"""Guided OpenClaw host onboarding for Twinbox."""

from __future__ import annotations

import getpass
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .env_writer import load_env_file, merge_env_file, write_env_file
from .llm import LLMError, resolve_backend
from .mail_env_contract import missing_required_mail_values
from .onboarding import STAGE_ORDER, load_state, save_state
from .openclaw_deploy import run_openclaw_deploy
from .openclaw_deploy_types import OpenClawDeployReport
from .openclaw_json_io import default_openclaw_fragment_path
from .paths import PathResolutionError, resolve_code_root, resolve_state_root

InputFn = Callable[[str], str]
SecretInputFn = Callable[[str], str]
DeployRunner = Callable[..., OpenClawDeployReport]


@dataclass
class OpenClawOnboardReport:
    ok: bool
    code_root: str = ""
    openclaw_home: str = ""
    state_root: str = ""
    mailbox: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    fragment: dict[str, Any] = field(default_factory=dict)
    deploy: dict[str, Any] = field(default_factory=dict)
    onboarding: dict[str, Any] = field(default_factory=dict)
    next_action: str = ""
    error: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code_root": self.code_root,
            "openclaw_home": self.openclaw_home,
            "state_root": self.state_root,
            "mailbox": self.mailbox,
            "llm": self.llm,
            "fragment": self.fragment,
            "deploy": self.deploy,
            "onboarding": self.onboarding,
            "next_action": self.next_action,
            "error": self.error,
            "notes": self.notes,
        }


def _prompt_text(input_fn: InputFn, prompt: str) -> str:
    return input_fn(prompt).strip()


def _prompt_secret(secret_input_fn: SecretInputFn, prompt: str) -> str:
    return secret_input_fn(prompt).strip()


def _prompt_choice(input_fn: InputFn, prompt: str, choices: tuple[str, ...]) -> str:
    allowed = {choice.lower(): choice for choice in choices}
    while True:
        raw = input_fn(prompt).strip().lower()
        if raw in allowed:
            return allowed[raw]


def _prompt_yes_no(input_fn: InputFn, prompt: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input_fn(f"{prompt} {suffix} ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def _set_stage_if_earlier(state, target: str) -> None:
    current_idx = STAGE_ORDER.index(state.current_stage)
    target_idx = STAGE_ORDER.index(target)
    if current_idx < target_idx:
        state.current_stage = target


def _sync_onboarding_state(state_root: Path, *, mailbox_ready: bool, llm_ready: bool, dry_run: bool) -> dict[str, Any]:
    state = load_state(state_root)
    previous_stage = state.current_stage

    if dry_run:
        current_stage = previous_stage
        if mailbox_ready and llm_ready and STAGE_ORDER.index(current_stage) < STAGE_ORDER.index("profile_setup"):
            current_stage = "profile_setup"
        elif mailbox_ready and STAGE_ORDER.index(current_stage) < STAGE_ORDER.index("llm_setup"):
            current_stage = "llm_setup"
        return {
            "previous_stage": previous_stage,
            "current_stage": current_stage,
            "completed_stages": list(state.completed_stages),
            "updated": current_stage != previous_stage,
        }

    if mailbox_ready:
        if "mailbox_login" not in state.completed_stages:
            state.completed_stages.append("mailbox_login")
        _set_stage_if_earlier(state, "llm_setup")
    if llm_ready:
        if "mailbox_login" not in state.completed_stages:
            state.completed_stages.append("mailbox_login")
        if "llm_setup" not in state.completed_stages:
            state.completed_stages.append("llm_setup")
        _set_stage_if_earlier(state, "profile_setup")

    save_state(state_root, state)
    return {
        "previous_stage": previous_stage,
        "current_stage": state.current_stage,
        "completed_stages": list(state.completed_stages),
        "updated": state.current_stage != previous_stage,
    }


def run_openclaw_onboard(
    *,
    code_root: Path | None = None,
    openclaw_home: Path | None = None,
    dry_run: bool = False,
    openclaw_bin: str = "openclaw",
    input_fn: InputFn | None = None,
    secret_input_fn: SecretInputFn | None = None,
    deploy_runner: DeployRunner = run_openclaw_deploy,
) -> OpenClawOnboardReport:
    report = OpenClawOnboardReport(ok=False)
    input_fn = input_fn or input
    secret_input_fn = secret_input_fn or getpass.getpass

    try:
        resolved_code_root = resolve_code_root(code_root or Path.cwd())
    except PathResolutionError as exc:
        report.error = str(exc)
        return report

    default_state_root = Path.home() / ".twinbox"
    try:
        configured_default = (
            Path(os.environ["TWINBOX_STATE_ROOT"]).expanduser()
            if "TWINBOX_STATE_ROOT" in os.environ
            else default_state_root
        )
        state_root = resolve_state_root(configured_default)
    except PathResolutionError:
        state_root = Path(os.environ.get("TWINBOX_STATE_ROOT", str(default_state_root))).expanduser()

    resolved_openclaw_home = (openclaw_home or Path.home() / ".openclaw").expanduser()
    report.code_root = str(resolved_code_root)
    report.state_root = str(state_root)
    report.openclaw_home = str(resolved_openclaw_home)

    if shutil.which(openclaw_bin) is None:
        report.error = f"Missing executable on PATH: {openclaw_bin}"
        return report

    env_file = state_root / ".env"
    dotenv = load_env_file(env_file)

    missing_mail = missing_required_mail_values(dotenv)
    mailbox_ready = not missing_mail
    report.mailbox = {
        "prompted": False,
        "configured": mailbox_ready,
        "missing_required": missing_mail,
        "status": "configured" if mailbox_ready else "missing",
        "mail_address": dotenv.get("MAIL_ADDRESS", ""),
        "env_file_path": str(env_file),
    }

    if not mailbox_ready:
        from .mailbox import run_preflight
        from .mailbox_detect import detect_to_env

        email = _prompt_text(input_fn, "Mailbox email: ")
        if not email:
            report.error = "Mailbox email is required."
            return report
        password = _prompt_secret(secret_input_fn, "Mailbox app password: ")
        if not password:
            report.error = "Mailbox password is required."
            return report
        detected = detect_to_env(email, verbose=False)
        if detected is None:
            report.error = f"Could not auto-detect mailbox servers for {email}"
            return report
        updates = {
            "MAIL_ADDRESS": email,
            "IMAP_HOST": detected["IMAP_HOST"],
            "IMAP_PORT": detected["IMAP_PORT"],
            "IMAP_ENCRYPTION": detected["IMAP_ENCRYPTION"],
            "IMAP_LOGIN": email,
            "IMAP_PASS": password,
            "SMTP_HOST": detected["SMTP_HOST"],
            "SMTP_PORT": detected["SMTP_PORT"],
            "SMTP_ENCRYPTION": detected["SMTP_ENCRYPTION"],
            "SMTP_LOGIN": email,
            "SMTP_PASS": password,
        }
        if not dry_run:
            write_env_file(env_file, merge_env_file(env_file, updates))
        exit_code, preflight = run_preflight(state_root=state_root)
        mailbox_ready = exit_code == 0
        report.mailbox = {
            "prompted": True,
            "configured": mailbox_ready,
            "missing_required": [],
            "status": preflight.get("status", "unknown"),
            "login_stage": preflight.get("login_stage", ""),
            "mail_address": email,
            "env_file_path": str(env_file),
        }
        if not mailbox_ready:
            report.error = "Mailbox setup failed preflight."
            return report
        dotenv = load_env_file(env_file)

    llm_ready = True
    try:
        backend = resolve_backend(env_file=env_file, env={})
        report.llm = {
            "prompted": False,
            "configured": True,
            "backend": backend.backend,
            "model": backend.model,
            "url": backend.url,
        }
    except LLMError:
        llm_ready = False
        provider = _prompt_choice(input_fn, "LLM provider [openai/anthropic]: ", ("openai", "anthropic"))
        api_key = _prompt_secret(secret_input_fn, "LLM API key: ")
        if not api_key:
            report.error = "LLM API key is required."
            return report
        updates = {"LLM_API_KEY": api_key} if provider == "openai" else {"ANTHROPIC_API_KEY": api_key}
        if not dry_run:
            write_env_file(env_file, merge_env_file(env_file, updates))
        try:
            backend = resolve_backend(env_file=env_file, env=updates if dry_run else {})
        except LLMError as exc:
            report.error = str(exc)
            return report
        llm_ready = True
        report.llm = {
            "prompted": True,
            "configured": True,
            "backend": backend.backend,
            "model": backend.model,
            "url": backend.url,
        }

    fragment_path = default_openclaw_fragment_path(resolved_code_root)
    use_fragment = False
    if fragment_path.is_file():
        use_fragment = _prompt_yes_no(
            input_fn,
            f"Include OpenClaw fragment from {fragment_path}?",
            default=True,
        )
    report.fragment = {
        "path": str(fragment_path),
        "exists": fragment_path.is_file(),
        "selected": use_fragment,
    }

    deploy_report = deploy_runner(
        code_root=resolved_code_root,
        openclaw_home=resolved_openclaw_home,
        dry_run=dry_run,
        restart_gateway=True,
        sync_env_from_dotenv=True,
        strict=True,
        fragment_path=fragment_path if use_fragment else None,
        no_fragment=fragment_path.is_file() and not use_fragment,
        openclaw_bin=openclaw_bin,
    )
    report.deploy = deploy_report.to_json_dict()
    if not deploy_report.ok:
        report.error = "OpenClaw deploy wiring failed."
        report.onboarding = _sync_onboarding_state(
            state_root,
            mailbox_ready=mailbox_ready,
            llm_ready=llm_ready,
            dry_run=dry_run,
        )
        return report

    report.onboarding = _sync_onboarding_state(
        state_root,
        mailbox_ready=mailbox_ready,
        llm_ready=llm_ready,
        dry_run=dry_run,
    )
    report.ok = True
    report.next_action = (
        "Continue inside OpenClaw with the twinbox agent; next conversational stage is "
        f"{report.onboarding['current_stage']}."
    )
    report.notes.append(
        "Host wiring is verified locally; OpenClaw session prompt injection can still lag behind on some models."
    )
    return report


def format_openclaw_onboard_report(report: OpenClawOnboardReport) -> str:
    lines = [
        "Twinbox OpenClaw onboard",
        f"result: {'ok' if report.ok else 'failed'}",
        f"state_root: {report.state_root}",
        f"mailbox: {report.mailbox.get('status', 'unknown')}",
        f"llm: {report.llm.get('backend', 'unconfigured')}",
        f"onboarding stage: {report.onboarding.get('current_stage', 'unknown')}",
    ]
    if report.error:
        lines.append(f"error: {report.error}")
    if report.next_action:
        lines.append(f"next: {report.next_action}")
    return "\n".join(lines)
