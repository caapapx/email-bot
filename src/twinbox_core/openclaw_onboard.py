"""Guided OpenClaw host onboarding for Twinbox."""

from __future__ import annotations

import getpass
import os
import shutil
import sys
import termios
import threading
import time
import textwrap
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, TextIO

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


class JourneyPrompter(Protocol):
    def intro(self, text: str) -> None: ...

    def outro(self, text: str) -> None: ...

    def note(self, title: str, body: str) -> None: ...

    def select(self, prompt: str, options: list[dict[str, str]], *, default: str | None = None) -> str: ...

    def confirm(self, prompt: str, *, default: bool = True) -> bool: ...

    def progress(self, title: str): ...


class ConsoleJourneyPrompter:
    _SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        input_fn: Callable[[str], str] | None = None,
        key_reader: Callable[[], str] | None = None,
        width: int | None = None,
    ) -> None:
        self._stream = stream or sys.stdout
        self._input_fn = input_fn or input
        self._key_reader = key_reader
        self._is_tty = hasattr(self._stream, "isatty") and self._stream.isatty()
        self._stdin_is_tty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
        self._spinner_idx = 0
        detected_width = width or shutil.get_terminal_size((80, 20)).columns
        self._width = max(32, detected_width)

    def _write(self, text: str = "") -> None:
        self._stream.write(text + "\n")
        self._stream.flush()

    def _write_inline(self, text: str) -> None:
        self._stream.write(text)
        self._stream.flush()

    def _style(self, text: str, code: str) -> str:
        if not self._is_tty:
            return text
        return f"\033[{code}m{text}\033[0m"

    def _next_spinner_frame(self) -> str:
        frame = self._SPINNER_FRAMES[self._spinner_idx % len(self._SPINNER_FRAMES)]
        self._spinner_idx += 1
        return frame

    def _wrap_text(self, text: str, width: int) -> list[str]:
        if not text:
            return [""]
        wrapped: list[str] = []
        for raw_line in text.splitlines() or [text]:
            chunks = textwrap.wrap(
                raw_line,
                width=max(8, width),
                break_long_words=False,
                break_on_hyphens=False,
            )
            wrapped.extend(chunks or [""])
        return wrapped or [""]

    def _clear_previous_frame(self, line_count: int) -> None:
        if line_count <= 0:
            return
        self._write_inline(f"\033[{line_count}A")
        for idx in range(line_count):
            self._write_inline("\r\033[2K")
            if idx < line_count - 1:
                self._write_inline("\033[1B")
        if line_count > 1:
            self._write_inline(f"\033[{line_count - 1}A")
        self._write_inline("\r")

    def _read_key(self) -> str:
        if self._key_reader is not None:
            return self._key_reader()
        if not self._stdin_is_tty:
            return ""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
            if char in ("\r", "\n"):
                return "ENTER"
            if char == "\x1b":
                next_char = sys.stdin.read(1)
                if next_char == "[":
                    arrow = sys.stdin.read(1)
                    return {"A": "UP", "B": "DOWN"}.get(arrow, "")
                return ""
            if char in ("k", "K"):
                return "UP"
            if char in ("j", "J"):
                return "DOWN"
            return char
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _render_select_frame(
        self,
        prompt: str,
        options: list[dict[str, str]],
        current_index: int,
        *,
        first_frame: bool,
        default: str | None,
    ) -> int:
        lines: list[str] = []
        body_width = max(24, self._width - 4)
        lines.append(self._style(prompt, "1"))
        lines.append("Use ↑/↓ to move. Press Enter to confirm.")
        for idx, opt in enumerate(options):
            label = opt.get("label", opt["value"]).strip()
            suffix = " [Recommended]" if opt.get("value") == default else ""
            pointer = "›" if idx == current_index else " "
            option_line = f"{pointer} {label}{suffix}"
            lines.append(self._style(option_line, "1;36" if idx == current_index else "0"))
            description = opt.get("description", "").strip()
            if description:
                for chunk in self._wrap_text(description, body_width):
                    prefix = "  "
                    rendered = f"{prefix}{chunk}"
                    lines.append(self._style(rendered, "36" if idx == current_index else "0"))

        if not first_frame:
            self._clear_previous_frame(len(lines))
        for line in lines:
            self._write(line)
        return len(lines)

    def intro(self, text: str) -> None:
        title = self._style(text, "1;36")
        border = self._style("━" * min(max(len(text), 28), self._width), "36")
        self._write("")
        self._write(border)
        self._write(title)
        self._write(border)
        self._write("")

    def outro(self, text: str) -> None:
        self._write("")
        self._write(self._style(text, "1;32"))
        self._write("")

    def note(self, title: str, body: str) -> None:
        content_width = max(24, self._width - 4)
        title_lines = self._wrap_text(title, content_width)
        body_lines = self._wrap_text(body, content_width)
        top = f"┌{'─' * (content_width + 2)}┐"
        divider = f"├{'─' * (content_width + 2)}┤"
        bottom = f"└{'─' * (content_width + 2)}┘"
        self._write(top)
        for title_line in title_lines:
            self._write(self._style(f"│ {title_line.ljust(content_width)} │", "1;34"))
        self._write(divider)
        for line in body_lines:
            self._write(f"│ {line.ljust(content_width)} │")
        self._write(bottom)
        self._write("")

    def select(self, prompt: str, options: list[dict[str, str]], *, default: str | None = None) -> str:
        if self._is_tty and (self._key_reader is not None or self._stdin_is_tty):
            values = [opt["value"] for opt in options]
            try:
                current_index = values.index(default) if default is not None else 0
            except ValueError:
                current_index = 0
            rendered_line_count = self._render_select_frame(
                prompt, options, current_index, first_frame=True, default=default
            )
            while True:
                key = self._read_key()
                if key == "UP":
                    current_index = (current_index - 1) % len(options)
                    rendered_line_count = self._render_select_frame(
                        prompt, options, current_index, first_frame=False, default=default
                    )
                elif key == "DOWN":
                    current_index = (current_index + 1) % len(options)
                    rendered_line_count = self._render_select_frame(
                        prompt, options, current_index, first_frame=False, default=default
                    )
                elif key == "ENTER":
                    self._write("")
                    return options[current_index]["value"]

        self._write(self._style(prompt, "1"))
        allowed: dict[str, str] = {}
        default_value = default
        for idx, opt in enumerate(options, 1):
            label = opt.get("label", opt["value"]).strip()
            suffix = " [Recommended]" if opt.get("value") == default_value else ""
            self._write(f"{idx}. {label}{suffix}")
            description = opt.get("description", "").strip()
            if description:
                self._write(f"   {description}")
            allowed[str(idx)] = opt["value"]
            allowed[opt["value"]] = opt["value"]
            allowed[label.lower()] = opt["value"]
        while True:
            self._write_inline("Enter choice: ")
            raw = self._input_fn("").strip()
            if not raw and default is not None:
                return default
            normalized = raw.lower()
            if normalized in allowed:
                return allowed[normalized]
            self._write(self._style("Invalid choice. Please enter a number or option name from the list above.", "31"))

    def confirm(self, prompt: str, *, default: bool = True) -> bool:
        return _prompt_yes_no(self._input_fn, prompt, default=default)

    def progress(self, title: str):
        stop_event = threading.Event()
        current_message = {"text": title}

        def _render_line() -> None:
            frame = self._next_spinner_frame()
            self._write_inline(self._style(f"\r{frame} {current_message['text']}", "1;33"))

        if self._is_tty:
            _render_line()

            def _spin() -> None:
                while not stop_event.wait(0.08):
                    _render_line()

            thread = threading.Thread(target=_spin, daemon=True)
            thread.start()
        else:
            thread = None
            self._write(self._style(f"… {title}", "1;33"))
        prompter = self

        class _Progress:
            def update(self, message: str) -> None:
                if prompter._is_tty:
                    current_message["text"] = message
                    _render_line()
                else:
                    prompter._write(f"  {message}")

            def finish(self, message: str) -> None:
                if prompter._is_tty:
                    stop_event.set()
                    if thread is not None:
                        thread.join(timeout=0.2)
                    prompter._write_inline("\r\033[K")
                prompter._write(prompter._style(f"  OK: {message}", "32"))

            def fail(self, message: str) -> None:
                if prompter._is_tty:
                    stop_event.set()
                    if thread is not None:
                        thread.join(timeout=0.2)
                    prompter._write_inline("\r\033[K")
                prompter._write(prompter._style(f"  FAIL: {message}", "31"))

        return _Progress()


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
    fragment_decision: bool | None = None,
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
        if fragment_decision is None:
            use_fragment = _prompt_yes_no(
                input_fn,
                f"Include OpenClaw fragment from {fragment_path}?",
                default=True,
            )
        else:
            use_fragment = fragment_decision
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


def run_openclaw_onboard_v2(
    *,
    code_root: Path | None = None,
    openclaw_home: Path | None = None,
    dry_run: bool = False,
    openclaw_bin: str = "openclaw",
    prompter: JourneyPrompter | None = None,
    run_onboard: Callable[..., OpenClawOnboardReport] = run_openclaw_onboard,
) -> OpenClawOnboardReport:
    prompter = prompter or ConsoleJourneyPrompter()
    resolved_code_root = None
    try:
        resolved_code_root = resolve_code_root(code_root or Path.cwd())
    except PathResolutionError:
        resolved_code_root = None

    fragment_path = default_openclaw_fragment_path(resolved_code_root) if resolved_code_root else None
    fragment_exists = bool(fragment_path and fragment_path.is_file())

    prompter.intro("Twinbox OpenClaw onboarding")
    prompter.note(
        "Phase 1 of 2",
        "This wizard verifies host wiring first, then hands you off to the twinbox agent for profile, materials, rules, and notifications.",
    )

    flow = prompter.select(
        "Choose onboarding flow",
        options=[
            {"value": "quickstart", "label": "Quickstart"},
            {"value": "advanced", "label": "Advanced"},
        ],
        default="quickstart",
    )

    if flow == "advanced":
        prompter.note(
            "Advanced mode",
            "You can review optional fragment behavior before Twinbox performs the recommended OpenClaw wiring sequence.",
        )

    fragment_decision: bool | None = None
    if fragment_exists:
        if flow == "quickstart":
            fragment_decision = True
            prompter.note(
                "Quickstart defaults",
                f"Twinbox will include the detected OpenClaw fragment at {fragment_path} so plugin wiring stays on the recommended path.",
            )
        else:
            fragment_decision = prompter.confirm(
                f"Include the detected OpenClaw fragment from {fragment_path}?",
                default=True,
            )

    progress = prompter.progress("Running Twinbox host onboarding")
    progress.update("Checking mailbox, LLM, and OpenClaw wiring prerequisites")
    report = run_onboard(
        code_root=code_root,
        openclaw_home=openclaw_home,
        dry_run=dry_run,
        openclaw_bin=openclaw_bin,
        fragment_decision=fragment_decision,
    )

    if report.ok:
        progress.finish("Host wiring verified and onboarding handoff prepared")
        current_stage = report.onboarding.get("current_stage", "unknown")
        prompter.note(
            "Phase 2 of 2",
            f"Continue in the twinbox agent inside OpenClaw. Your next guided conversation stage is {current_stage}.",
        )
        prompter.outro(
            "Continue in the twinbox agent now. Ask it to keep onboarding and it should pick up from the next stage."
        )
    else:
        progress.fail(report.error or "OpenClaw host onboarding failed")
        current_stage = report.onboarding.get("current_stage", "unknown")
        prompter.note(
            "Recovery",
            f"Twinbox stopped during host setup. Current guided stage is {current_stage}; fix the blocking error, then rerun the wizard.",
        )
        prompter.outro(report.error or "Onboarding failed before handoff.")

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
