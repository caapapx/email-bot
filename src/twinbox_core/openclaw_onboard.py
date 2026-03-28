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

    def cancel(self, summary_title: str, summary_value: str, message: str = "Setup cancelled.") -> None: ...

    def note(self, title: str, body: str) -> None: ...

    def select(
        self,
        prompt: str,
        options: list[dict[str, str]],
        *,
        default: str | None = None,
        layout: str = "vertical",
    ) -> str: ...

    def text(self, prompt: str, *, default: str | None = None) -> str: ...

    def secret(self, prompt: str, *, allow_empty: bool = False) -> str: ...

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

    def _dim_preview(self, text: str) -> str:
        return self._style(text, "90")

    def _muted(self, text: str) -> str:
        return self._style(text, "38;5;244")

    def _accent(self, text: str) -> str:
        return self._style(text, "1;38;5;208")

    def _banner_lines(self) -> list[str]:
        raw_lines = [
            "  TWINBOX  ",
            "  TWINBOX  ",
        ]
        if not self._is_tty:
            return ["TWINBOX"]
        return [self._style(line, "1;30;47") for line in raw_lines]

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
            key = self._key_reader()
            if key in {"\x03", "CTRL_C"}:
                raise KeyboardInterrupt
            return key
        if not self._stdin_is_tty:
            return ""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
            if char in ("\r", "\n"):
                return "ENTER"
            if char == "\x03":
                raise KeyboardInterrupt
            if char == "\x1b":
                next_char = sys.stdin.read(1)
                if next_char == "[":
                    arrow = sys.stdin.read(1)
                    return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(arrow, "")
                return ""
            if char in ("k", "K"):
                return "UP"
            if char in ("j", "J"):
                return "DOWN"
            if char in ("h", "H"):
                return "LEFT"
            if char in ("l", "L"):
                return "RIGHT"
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
        layout: str,
    ) -> int:
        lines: list[str] = []
        body_width = max(24, self._width - 4)
        lines.append(self._style(prompt, "1"))
        if layout == "horizontal":
            lines.append("Use ←/→ to move. Press Enter to confirm.")
            rendered_options: list[str] = []
            for idx, opt in enumerate(options):
                label = opt.get("label", opt["value"]).strip()
                selected = idx == current_index
                glyph = opt.get("selected_glyph" if selected else "unselected_glyph")
                if not glyph:
                    glyph = "●" if selected else "○"
                rendered = f"{glyph} {label}"
                rendered_options.append(self._style(rendered, "1;32" if selected else "0"))
            lines.append(" / ".join(rendered_options))
        else:
            lines.append("Use ↑/↓ to move. Press Enter to confirm.")
            for idx, opt in enumerate(options):
                label = opt.get("label", opt["value"]).strip()
                pointer = "›" if idx == current_index else " "
                description = opt.get("description", "").strip() if idx == current_index else ""
                option_line = f"{pointer} {label}"
                if description:
                    option_line = f"{option_line} ({description})"
                wrapped = self._wrap_text(option_line, body_width)
                for line_index, chunk in enumerate(wrapped):
                    if line_index == 0:
                        rendered = chunk
                    else:
                        rendered = f"  {chunk}"
                    lines.append(self._style(rendered, "1;38;5;208" if idx == current_index else "0;37"))

        if not first_frame:
            self._clear_previous_frame(len(lines))
        for line in lines:
            self._write(line)
        return len(lines)

    def intro(self, text: str) -> None:
        brand = self._accent("✉ TwinBox v1")
        tagline = self._muted("Reads your inbox without making you babysit it.")
        self._write("")
        self._write(f"{brand} {self._muted('—')} {tagline}")
        self._write("")
        for line in self._banner_lines():
            self._write(line)
        self._write("")
        self._write(self._accent(text))
        self._write("")

    def outro(self, text: str) -> None:
        self._write("")
        self._write(self._style(text, "1;32"))
        self._write("")

    def cancel(self, summary_title: str, summary_value: str, message: str = "Setup cancelled.") -> None:
        accent = self._style("■", "1;38;5;208")
        summary = self._style(summary_title, "1;38;5;208")
        value = self._style(summary_value, "0;37")
        footer = self._style(message, "0;37")
        self._write("")
        self._write("│")
        self._write(f"{accent}  {summary}")
        self._write(f"│  {value}")
        self._write("│")
        self._write(f"└  {footer}")
        self._write("")

    def note(self, title: str, body: str) -> None:
        content_width = max(24, self._width - 6)
        title_lines = self._wrap_text(title, content_width)
        body_lines = self._wrap_text(body, content_width)
        rail = self._muted("│")
        elbow = self._muted("└")
        rule = self._muted("─" * min(28, content_width))
        self._write(f"{rail}")
        for title_line in title_lines:
            self._write(f"{rail}  {self._accent(title_line)}")
        self._write(f"{rail}")
        for line in body_lines:
            self._write(f"{rail}  {self._muted(line)}")
        self._write(f"{elbow}{rule}")
        self._write("")

    def select(
        self,
        prompt: str,
        options: list[dict[str, str]],
        *,
        default: str | None = None,
        layout: str = "vertical",
    ) -> str:
        if self._is_tty and (self._key_reader is not None or self._stdin_is_tty):
            values = [opt["value"] for opt in options]
            try:
                current_index = values.index(default) if default is not None else 0
            except ValueError:
                current_index = 0
            rendered_line_count = self._render_select_frame(
                prompt, options, current_index, first_frame=True, default=default, layout=layout
            )
            while True:
                key = self._read_key()
                if key in {"UP", "LEFT"}:
                    current_index = (current_index - 1) % len(options)
                    rendered_line_count = self._render_select_frame(
                        prompt, options, current_index, first_frame=False, default=default, layout=layout
                    )
                elif key in {"DOWN", "RIGHT"}:
                    current_index = (current_index + 1) % len(options)
                    rendered_line_count = self._render_select_frame(
                        prompt, options, current_index, first_frame=False, default=default, layout=layout
                    )
                elif key == "ENTER":
                    self._write("")
                    return options[current_index]["value"]

        self._write(self._style(prompt, "1"))
        allowed: dict[str, str] = {}
        default_value = default
        for idx, opt in enumerate(options, 1):
            label = opt.get("label", opt["value"]).strip()
            self._write(f"{idx}. {label}")
            description = opt.get("description", "").strip()
            if description:
                self._write(self._dim_preview(f"   ({description})"))
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

    def text(self, prompt: str, *, default: str | None = None) -> str:
        rendered_prompt = f"{prompt}: " if not default else f"{prompt} [{default}]: "
        raw = self._input_fn(rendered_prompt).strip()
        if not raw and default is not None:
            return default
        return raw

    def secret(self, prompt: str, *, allow_empty: bool = False) -> str:
        suffix = " (press Enter to keep current value)" if allow_empty else ""
        return _prompt_secret(getpass.getpass, f"{prompt}{suffix}: ")

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


def _mailbox_summary(dotenv: dict[str, str]) -> str:
    mail = dotenv.get("MAIL_ADDRESS") or "not configured"
    imap_host = dotenv.get("IMAP_HOST") or "not configured"
    smtp_host = dotenv.get("SMTP_HOST") or "not configured"
    imap_pass = "configured" if dotenv.get("IMAP_PASS") else "missing"
    smtp_pass = "configured" if dotenv.get("SMTP_PASS") else "missing"
    return (
        f"Current mailbox\n"
        f"- Email: {mail}\n"
        f"- IMAP host: {imap_host}\n"
        f"- SMTP host: {smtp_host}\n"
        f"- Passwords: IMAP {imap_pass}, SMTP {smtp_pass}"
    )


def _inspect_llm(env_file: Path, dotenv: dict[str, str]) -> dict[str, Any]:
    try:
        backend = resolve_backend(env_file=env_file, env={})
        return {
            "configured": True,
            "backend": backend.backend,
            "model": backend.model,
            "url": backend.url,
            "openai_key_configured": bool(dotenv.get("LLM_API_KEY")),
            "anthropic_key_configured": bool(dotenv.get("ANTHROPIC_API_KEY")),
        }
    except LLMError:
        return {
            "configured": False,
            "backend": "",
            "model": dotenv.get("LLM_MODEL") or dotenv.get("ANTHROPIC_MODEL", ""),
            "url": dotenv.get("LLM_API_URL") or dotenv.get("ANTHROPIC_BASE_URL", ""),
            "openai_key_configured": bool(dotenv.get("LLM_API_KEY")),
            "anthropic_key_configured": bool(dotenv.get("ANTHROPIC_API_KEY")),
        }


def _llm_summary(llm_info: dict[str, Any]) -> str:
    provider = llm_info.get("backend") or "not configured"
    model = llm_info.get("model") or "default"
    url = llm_info.get("url") or "default"
    key_state = "configured" if llm_info.get("configured") else "missing"
    return (
        f"Current LLM\n"
        f"- Provider: {provider}\n"
        f"- Model: {model}\n"
        f"- API URL: {url}\n"
        f"- API key: {key_state}"
    )


def _prompt_mailbox_customization(
    prompter: JourneyPrompter,
    *,
    dotenv: dict[str, str],
) -> dict[str, str]:
    mode = prompter.select(
        "How should Twinbox configure your mailbox?",
        options=[
            {
                "value": "auto",
                "label": "Auto-detect from email address, like ponyma@qq.com",
                "description": "Recommended for most personal inboxes. Twinbox will detect the server settings for you.",
            },
            {
                "value": "manual",
                "label": "Enter server settings manually",
                "description": "Use this if your provider needs custom IMAP or SMTP settings.",
            },
        ],
        default="auto",
    )

    if mode == "auto":
        email = prompter.text("Mailbox email address", default=dotenv.get("MAIL_ADDRESS"))
        password = prompter.secret(
            "Mailbox app password",
            allow_empty=bool(dotenv.get("IMAP_PASS") or dotenv.get("SMTP_PASS")),
        )
        if not email:
            raise ValueError("Mailbox email is required.")
        if not password and not (dotenv.get("IMAP_PASS") or dotenv.get("SMTP_PASS")):
            raise ValueError("Mailbox password is required.")
        from .mailbox_detect import detect_to_env

        detected = detect_to_env(email, verbose=False)
        if detected is None:
            raise ValueError(f"Could not auto-detect mailbox servers for {email}")
        existing_secret = dotenv.get("IMAP_PASS") or dotenv.get("SMTP_PASS", "")
        resolved_password = password or existing_secret
        return {
            "MAIL_ADDRESS": email,
            "IMAP_HOST": detected["IMAP_HOST"],
            "IMAP_PORT": detected["IMAP_PORT"],
            "IMAP_ENCRYPTION": detected["IMAP_ENCRYPTION"],
            "IMAP_LOGIN": dotenv.get("IMAP_LOGIN") or email,
            "IMAP_PASS": resolved_password,
            "SMTP_HOST": detected["SMTP_HOST"],
            "SMTP_PORT": detected["SMTP_PORT"],
            "SMTP_ENCRYPTION": detected["SMTP_ENCRYPTION"],
            "SMTP_LOGIN": dotenv.get("SMTP_LOGIN") or email,
            "SMTP_PASS": resolved_password,
        }

    email = prompter.text("Mailbox email address", default=dotenv.get("MAIL_ADDRESS"))
    imap_host = prompter.text("IMAP host", default=dotenv.get("IMAP_HOST"))
    imap_port = prompter.text("IMAP port", default=dotenv.get("IMAP_PORT", "993"))
    imap_encryption = prompter.text("IMAP encryption", default=dotenv.get("IMAP_ENCRYPTION", "ssl"))
    imap_login = prompter.text("IMAP login", default=dotenv.get("IMAP_LOGIN") or email)
    imap_pass = prompter.secret("IMAP password", allow_empty=bool(dotenv.get("IMAP_PASS")))
    smtp_host = prompter.text("SMTP host", default=dotenv.get("SMTP_HOST"))
    smtp_port = prompter.text("SMTP port", default=dotenv.get("SMTP_PORT", "465"))
    smtp_encryption = prompter.text("SMTP encryption", default=dotenv.get("SMTP_ENCRYPTION", "ssl"))
    smtp_login = prompter.text("SMTP login", default=dotenv.get("SMTP_LOGIN") or email)
    smtp_pass = prompter.secret("SMTP password", allow_empty=bool(dotenv.get("SMTP_PASS") or dotenv.get("IMAP_PASS")))
    if not email:
        raise ValueError("Mailbox email is required.")
    resolved_imap_pass = imap_pass or dotenv.get("IMAP_PASS", "")
    resolved_smtp_pass = smtp_pass or dotenv.get("SMTP_PASS") or resolved_imap_pass
    if not resolved_imap_pass or not resolved_smtp_pass:
        raise ValueError("Mailbox password is required.")
    return {
        "MAIL_ADDRESS": email,
        "IMAP_HOST": imap_host,
        "IMAP_PORT": imap_port,
        "IMAP_ENCRYPTION": imap_encryption,
        "IMAP_LOGIN": imap_login,
        "IMAP_PASS": resolved_imap_pass,
        "SMTP_HOST": smtp_host,
        "SMTP_PORT": smtp_port,
        "SMTP_ENCRYPTION": smtp_encryption,
        "SMTP_LOGIN": smtp_login,
        "SMTP_PASS": resolved_smtp_pass,
    }


def _apply_mailbox_updates(
    *,
    state_root: Path,
    env_file: Path,
    dotenv: dict[str, str],
    updates: dict[str, str] | None,
    dry_run: bool,
) -> tuple[bool, dict[str, Any], dict[str, str]]:
    from .mailbox import run_preflight

    merged = dict(dotenv)
    if updates:
        merged.update(updates)
        if not dry_run:
            write_env_file(env_file, merged)
    if dry_run:
        preflight = {
            "status": "dry_run",
            "login_stage": "mailbox-dry-run",
        }
        ready = True
    else:
        exit_code, preflight = run_preflight(state_root=state_root)
        ready = exit_code == 0
        merged = load_env_file(env_file)
    return (
        ready,
        {
            "prompted": bool(updates),
            "configured": ready,
            "missing_required": [] if ready else missing_required_mail_values(merged),
            "status": preflight.get("status", "unknown"),
            "login_stage": preflight.get("login_stage", ""),
            "mail_address": merged.get("MAIL_ADDRESS", ""),
            "env_file_path": str(env_file),
        },
        merged,
    )


def _provider_env_keys(provider: str) -> tuple[str, str, str]:
    if provider == "anthropic":
        return ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL")
    return ("LLM_API_KEY", "LLM_MODEL", "LLM_API_URL")


def _opposite_provider_keys(provider: str) -> tuple[str, str, str]:
    return _provider_env_keys("openai" if provider == "anthropic" else "anthropic")


def _apply_llm_updates(
    *,
    env_file: Path,
    dotenv: dict[str, str],
    provider: str,
    api_key: str,
    model: str,
    api_url: str,
    dry_run: bool,
) -> tuple[bool, dict[str, Any], dict[str, str]]:
    key_name, model_name, url_name = _provider_env_keys(provider)
    opposite_key, opposite_model, opposite_url = _opposite_provider_keys(provider)
    merged = dict(dotenv)
    merged[key_name] = api_key
    if model:
        merged[model_name] = model
    elif model_name in merged:
        merged.pop(model_name, None)
    if api_url:
        merged[url_name] = api_url
    elif url_name in merged:
        merged.pop(url_name, None)
    merged.pop(opposite_key, None)
    merged.pop(opposite_model, None)
    merged.pop(opposite_url, None)
    if not dry_run:
        write_env_file(env_file, merged)
    try:
        backend = resolve_backend(env_file=env_file, env=merged if dry_run else {})
    except LLMError as exc:
        return (
            False,
            {
                "prompted": True,
                "configured": False,
                "backend": provider,
                "model": model,
                "url": api_url,
                "error": str(exc),
            },
            merged,
        )
    return (
        True,
        {
            "prompted": True,
            "configured": True,
            "backend": backend.backend,
            "model": backend.model,
            "url": backend.url,
        },
        merged,
    )


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
    deploy_runner: DeployRunner | None = None,
    run_onboard: Callable[..., OpenClawOnboardReport] = run_openclaw_onboard,
) -> OpenClawOnboardReport:
    del run_onboard
    prompter = prompter or ConsoleJourneyPrompter()
    deploy_runner = deploy_runner or run_openclaw_deploy
    report = OpenClawOnboardReport(ok=False)
    flow_label = "Quickstart"
    try:
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
        fragment_path = default_openclaw_fragment_path(resolved_code_root)
        fragment_exists = fragment_path.is_file()

        prompter.intro("TwinBox setup")
        prompter.note(
        "TwinBox setup",
        "Phase 1 of 2. This wizard verifies host wiring first, then hands you off to the twinbox agent for profile, materials, rules, and notifications.",
        )
        prompter.note(
        "Security",
        (
            "Twinbox is personal-by-default. Please use this setup only where mailbox access, prompts, and attached tools are trusted.\n\n"
            "Shared or multi-user setups need extra lock-down before you rely on them."
        ),
        )
        security_choice = prompter.select(
        "I understand this is personal-by-default and shared/multi-user use requires lock-down. Continue?",
        options=[
            {
                "value": "continue",
                "label": "Yes",
                "selected_glyph": "●",
                "unselected_glyph": "○",
            },
            {
                "value": "cancel",
                "label": "No",
                "selected_glyph": "●",
                "unselected_glyph": "○",
            },
        ],
        default="continue",
        layout="horizontal",
        )
        if security_choice != "continue":
            report.error = "Security acknowledgement was not accepted."
            report.onboarding = _sync_onboarding_state(
            state_root,
            mailbox_ready=False,
            llm_ready=False,
            dry_run=dry_run,
            )
            prompter.outro("Setup stopped before any host changes were applied.")
            return report

        flow = prompter.select(
        "Choose onboarding flow",
        options=[
            {"value": "quickstart", "label": "Quickstart", "description": "Follow the recommended setup path with the fewest decisions."},
            {"value": "advanced", "label": "Manual", "description": "Configure port, network, Tailscale, and auth options."},
        ],
        default="quickstart",
        )
        flow_label = "Manual" if flow == "advanced" else "Quickstart"
        advanced = flow == "advanced"

        missing_mail = missing_required_mail_values(dotenv)
        mailbox_ready = not missing_mail
        mailbox_body = (
            f"{_mailbox_summary(dotenv)}\n\n"
            "Twinbox needs mailbox access before the agent can keep onboarding."
        )
        if advanced:
            mailbox_body += f"\n\nState file: {env_file}"
        prompter.note("Mailbox", mailbox_body)
        if mailbox_ready:
            mailbox_action = prompter.select(
                "Choose mailbox setup",
                options=[
                    {"value": "use_current_mailbox", "label": "Use current value", "description": "Validate the mailbox settings already stored in Twinbox."},
                    {"value": "customize_mailbox", "label": "Customize", "description": "Review or replace the mailbox settings before continuing."},
                ],
                default="use_current_mailbox" if flow == "quickstart" else "customize_mailbox",
            )
        else:
            mailbox_action = "customize_mailbox"
        mailbox_progress = prompter.progress("Checking mailbox settings")
        try:
            mailbox_updates = None
            if mailbox_action == "customize_mailbox":
                mailbox_progress.update("Collecting mailbox configuration")
                mailbox_updates = _prompt_mailbox_customization(prompter, dotenv=dotenv)
            mailbox_ready, report.mailbox, dotenv = _apply_mailbox_updates(
                state_root=state_root,
                env_file=env_file,
                dotenv=dotenv,
                updates=mailbox_updates,
                dry_run=dry_run,
            )
        except ValueError as exc:
            mailbox_progress.fail(str(exc))
            report.error = str(exc)
            report.mailbox = {
                "prompted": mailbox_action == "customize_mailbox",
                "configured": False,
                "missing_required": missing_required_mail_values(dotenv),
                "status": "error",
                "mail_address": dotenv.get("MAIL_ADDRESS", ""),
                "env_file_path": str(env_file),
            }
            report.onboarding = _sync_onboarding_state(
                state_root,
                mailbox_ready=False,
                llm_ready=False,
                dry_run=dry_run,
            )
            prompter.note(
                "Recovery",
                "Mailbox setup is required before Twinbox can continue. Fix the mailbox step and rerun the wizard.",
            )
            prompter.outro(report.error)
            return report
        if not mailbox_ready:
            mailbox_progress.fail("Mailbox validation did not pass")
            report.error = "Mailbox validation failed."
            report.onboarding = _sync_onboarding_state(
                state_root,
                mailbox_ready=False,
                llm_ready=False,
                dry_run=dry_run,
            )
            prompter.note(
                "Recovery",
                "Twinbox could not validate the mailbox settings. Review the mailbox values and rerun the wizard.",
            )
            prompter.outro(report.error)
            return report
        mailbox_progress.finish("Mailbox settings validated")

        llm_info = _inspect_llm(env_file, dotenv)
        llm_body = (
            f"{_llm_summary(llm_info)}\n\n"
            "Twinbox needs an LLM backend for the Phase 1-4 pipeline. Choose a provider to review or update it, or skip for now."
        )
        if llm_info.get("configured"):
            llm_body += "\nPress Enter on a field to keep the current model or API URL."
        prompter.note("LLM", llm_body)
        llm_choice = prompter.select(
            "Choose LLM setup",
            options=[
                {"value": "openai", "label": "Configure OpenAI", "description": "Use the OpenAI-compatible provider path."},
                {"value": "anthropic", "label": "Configure Anthropic", "description": "Use the Anthropic native messages API path."},
                {"value": "skip", "label": "Skip for now", "description": "Keep the current value if one exists, or leave this step incomplete for now."},
            ],
            default=llm_info.get("backend") or "openai",
        )
        llm_ready = bool(llm_info.get("configured"))
        if llm_choice == "skip":
            report.llm = {
                "prompted": False,
                "configured": llm_ready,
                "backend": llm_info.get("backend", ""),
                "model": llm_info.get("model", ""),
                "url": llm_info.get("url", ""),
                "status": "configured" if llm_ready else "skipped",
            }
        else:
            current_key_name, current_model_name, current_url_name = _provider_env_keys(llm_choice)
            current_key = dotenv.get(current_key_name, "")
            current_model = dotenv.get(current_model_name, "")
            current_url = dotenv.get(current_url_name, "")
            llm_progress = prompter.progress("Validating LLM configuration")
            api_key = prompter.secret("API key", allow_empty=bool(current_key))
            if not api_key:
                api_key = current_key
            if not api_key:
                llm_progress.fail("API key is required for the selected provider")
                report.error = "LLM API key is required."
                report.llm = {
                    "prompted": True,
                    "configured": False,
                    "backend": llm_choice,
                    "model": current_model,
                    "url": current_url,
                }
                report.onboarding = _sync_onboarding_state(
                    state_root,
                    mailbox_ready=mailbox_ready,
                    llm_ready=False,
                    dry_run=dry_run,
                )
                prompter.note(
                    "Recovery",
                    "Twinbox needs an API key before it can validate the selected LLM provider.",
                )
                prompter.outro(report.error)
                return report
            model = prompter.text("Model", default=current_model)
            api_url = prompter.text("API URL", default=current_url)
            llm_ready, report.llm, dotenv = _apply_llm_updates(
                env_file=env_file,
                dotenv=dotenv,
                provider=llm_choice,
                api_key=api_key,
                model=model,
                api_url=api_url,
                dry_run=dry_run,
            )
            if llm_ready:
                llm_progress.finish("LLM configuration validated")
            else:
                llm_progress.fail(report.llm.get("error", "LLM validation failed"))

        integration_body = (
            "This adds the small Twinbox integration config that helps OpenClaw discover Twinbox tools and stay on the recommended wiring path.\n\n"
            f"Integration fragment: {fragment_path if fragment_exists else 'not found'}"
        )
        if advanced:
            integration_body += f"\nOpenClaw home: {resolved_openclaw_home}"
        prompter.note("Twinbox tools integration", integration_body)
        if fragment_exists:
            fragment_selected = (
                prompter.select(
                    "Use the recommended Twinbox tools integration?",
                    options=[
                        {"value": "yes", "label": "Yes (Recommended)", "selected_glyph": "●", "unselected_glyph": "○"},
                        {"value": "no", "label": "No", "selected_glyph": "●", "unselected_glyph": "○"},
                    ],
                    default="yes",
                    layout="horizontal",
                )
                == "yes"
            )
        else:
            fragment_selected = False
        report.fragment = {
            "path": str(fragment_path),
            "exists": fragment_exists,
            "selected": fragment_selected,
        }

        summary_lines = [
            f"Mailbox: {report.mailbox.get('mail_address') or 'configured'}",
            f"LLM: {report.llm.get('backend') or report.llm.get('status', 'not configured')}",
            f"Twinbox tools integration: {'yes' if fragment_selected else 'no'}",
            f"Repo root: {resolved_code_root}",
            f"OpenClaw home: {resolved_openclaw_home}",
        ]
        if advanced:
            summary_lines.append(f"State root: {state_root}")
        prompter.note("Apply setup", "\n".join(summary_lines))
        deploy_choice = prompter.select(
            "Apply the host setup now?",
            options=[
                {"value": "apply", "label": "Apply now", "selected_glyph": "◆", "unselected_glyph": "◇"},
                {"value": "skip", "label": "Skip for now", "selected_glyph": "◆", "unselected_glyph": "◇"},
            ],
            default="apply",
            layout="horizontal",
        )
        if deploy_choice == "skip":
            report.deploy = {
                "ok": False,
                "status": "skipped",
            }
            report.onboarding = _sync_onboarding_state(
                state_root,
                mailbox_ready=mailbox_ready,
                llm_ready=llm_ready,
                dry_run=dry_run,
            )
            report.error = "Host setup was reviewed but not applied yet."
            report.next_action = (
                "Apply the host setup when you are ready, then continue inside OpenClaw with the twinbox agent; "
                f"next guided conversation stage is {report.onboarding['current_stage']}."
            )
            prompter.note(
                "Recovery",
                f"Host setup is still pending. Current guided stage is {report.onboarding['current_stage']}; apply the setup, then continue in the twinbox agent.",
            )
            prompter.outro(report.error)
            return report

        deploy_progress = prompter.progress("Applying Twinbox OpenClaw setup")
        deploy_progress.update("Syncing skill, config, fragment choice, and gateway wiring")
        deploy_report = deploy_runner(
            code_root=resolved_code_root,
            openclaw_home=resolved_openclaw_home,
            dry_run=dry_run,
            restart_gateway=True,
            sync_env_from_dotenv=True,
            strict=True,
            fragment_path=fragment_path if fragment_selected else None,
            no_fragment=fragment_exists and not fragment_selected,
            openclaw_bin=openclaw_bin,
        )
        report.deploy = deploy_report.to_json_dict()
        if not deploy_report.ok:
            deploy_progress.fail("OpenClaw deploy wiring failed")
            report.error = "OpenClaw deploy wiring failed."
            report.onboarding = _sync_onboarding_state(
                state_root,
                mailbox_ready=mailbox_ready,
                llm_ready=llm_ready,
                dry_run=dry_run,
            )
            prompter.note(
                "Recovery",
                f"Twinbox stopped during host setup. Current guided stage is {report.onboarding['current_stage']}; fix the deploy error, then rerun the wizard.",
            )
            prompter.outro(report.error)
            return report
        deploy_progress.finish("Host wiring applied")

        report.onboarding = _sync_onboarding_state(
            state_root,
            mailbox_ready=mailbox_ready,
            llm_ready=llm_ready,
            dry_run=dry_run,
        )
        current_stage = report.onboarding.get("current_stage", "unknown")
        if llm_ready:
            report.ok = True
            report.next_action = (
                "Continue inside OpenClaw with the twinbox agent; "
                f"next guided conversation stage is {current_stage}."
            )
            report.notes.append(
                "Host wiring is verified locally; OpenClaw session prompt injection can still lag behind on some models."
            )
            prompter.note(
                "Phase 2 of 2",
                f"Continue in the twinbox agent inside OpenClaw. Your next guided conversation stage is {current_stage}.",
            )
            prompter.outro(
                "Continue in the twinbox agent now. Ask it to keep onboarding and it should pick up from the next stage."
            )
            return report

        report.error = "LLM setup is still incomplete."
        report.next_action = (
            "Host setup is partially ready. Configure the LLM step, then continue inside OpenClaw with the twinbox agent; "
            f"next guided conversation stage is {current_stage}."
        )
        prompter.note(
            "Phase 2 of 2",
            f"Host setup is partially ready. Your next guided conversation stage is {current_stage}, but Twinbox still needs LLM setup before the full handoff is ready.",
        )
        prompter.outro("Finish the LLM step, then continue in the twinbox agent.")
        return report
    except KeyboardInterrupt:
        report.ok = False
        report.error = "Setup cancelled."
        prompter.cancel("Setup mode", flow_label)
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
