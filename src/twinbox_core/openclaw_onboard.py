"""Guided OpenClaw host onboarding for Twinbox."""

from __future__ import annotations

import getpass
import os
import re
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
from .twinbox_config import (
    config_path_for_state_root,
    load_twinbox_config,
    save_twinbox_config,
)

# README.md headline — keep in sync with repo branding.
_README_WORDMARK_TAGLINE = (
    "Thread-level email intelligence that keeps important things from drowning."
)

InputFn = Callable[[str], str]
SecretInputFn = Callable[[str], str]
DeployRunner = Callable[..., OpenClawDeployReport]
LLMUpdateRunner = Callable[..., tuple[bool, dict[str, Any], dict[str, str]]]
MailboxApplyRunner = Callable[..., tuple[bool, dict[str, Any], dict[str, str]]]


class JourneyPrompter(Protocol):
    def intro(self, text: str) -> None: ...

    def outro(self, text: str) -> None: ...

    def cancel(self, summary_title: str, summary_value: str, message: str = "Setup cancelled.") -> None: ...

    def note(self, title: str, body: str, *, complete: bool | None = None) -> None: ...

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

    def journey_rail_begin(self) -> None: ...


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
        self._journey_rail = False
        self._journey_gap_before_next_note = False

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

    def _style_parenthetical_chunk(
        self,
        text: str,
        *,
        main_code: str,
        paren_code: str = "0;90",
        initial_depth: int = 0,
        glyph: str | None = None,
        glyph_code: str | None = None,
    ) -> tuple[str, int]:
        if not self._is_tty:
            return text, initial_depth

        parts: list[str] = []
        depth = initial_depth
        index = 0
        if glyph and depth == 0 and text.startswith(glyph):
            parts.append(self._style(glyph, glyph_code or main_code))
            index = len(glyph)

        buffer: list[str] = []
        in_paren = depth > 0

        def flush(code: str) -> None:
            nonlocal buffer
            if buffer:
                parts.append(self._style("".join(buffer), code))
                buffer = []

        while index < len(text):
            ch = text[index]
            if ch == "(":
                if depth == 0:
                    if buffer and buffer[-1] == " ":
                        buffer.pop()
                        flush(main_code)
                        buffer = [" ", "("]
                    else:
                        flush(main_code)
                        buffer = ["("]
                    depth = 1
                    in_paren = True
                else:
                    buffer.append(ch)
                    depth += 1
                index += 1
                continue
            if ch == ")":
                buffer.append(ch)
                if depth > 0:
                    depth -= 1
                    if depth == 0:
                        flush(paren_code)
                        in_paren = False
                index += 1
                continue
            buffer.append(ch)
            index += 1

        flush(paren_code if in_paren else main_code)
        return "".join(parts), depth

    @staticmethod
    def _visible_length(text: str) -> int:
        plain = re.sub(r"\x1b\[[0-9;]*[mK]", "", text)
        n = len(plain)
        # Common emoji (e.g. 📮) occupy two terminal columns on typical emulators.
        for ch in plain:
            if 0x1F300 <= ord(ch) <= 0x1FAFF:
                n += 1
        return n

    def _pad_center_visual(self, styled_segment: str, inner_width: int) -> str:
        pad = max(0, (inner_width - self._visible_length(styled_segment)) // 2)
        return " " * pad + styled_segment

    def _pad_inner_row_exact(self, styled_segment: str, inner_width: int) -> str:
        """Pad to exact visual width so the right box border aligns (no stray-looking │)."""
        vis = self._visible_length(styled_segment)
        if vis >= inner_width:
            return styled_segment
        left = max(0, (inner_width - vis) // 2)
        right = inner_width - vis - left
        return " " * left + styled_segment + " " * right

    def _logo_frame_lines(self) -> list[str]:
        """README tagline + OpenClaw-style framed header; wordmark TWINBOX for CLI emphasis."""
        inner_w = min(68, max(44, self._width - 8))
        tagline_wrapped = self._wrap_text(_README_WORDMARK_TAGLINE, inner_w)

        if not self._is_tty:
            return [
                "",
                "TWINBOX 📮",
                "",
                *tagline_wrapped,
                "",
            ]

        m = self._muted
        bar = "─" * (inner_w + 2)
        # Large wordmark: wide inverse block + emoji; pad row so right │ is the box edge only.
        wordmark = self._style("    TWINBOX    ", "1;97;48;5;208") + "  📮"
        lines: list[str] = [
            "",
            m("╭" + bar + "╮"),
            m("│ ") + " " * inner_w + m(" │"),
            m("│ ") + self._pad_inner_row_exact(wordmark, inner_w) + m(" │"),
            m("│ ") + " " * inner_w + m(" │"),
        ]
        for tl in tagline_wrapped:
            lines.append(m("│ ") + self._muted(tl.ljust(inner_w)) + m(" │"))
        lines.append(m("│ ") + " " * inner_w + m(" │"))
        lines.append(m("╰" + bar + "╯"))
        return lines

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
        previous_height: int = 0,
        default: str | None,
        layout: str,
    ) -> int:
        lines: list[str] = []
        body_width = max(24, self._width - 4)
        lines.append(self._accent(prompt))
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
                styled, _ = self._style_parenthetical_chunk(
                    rendered,
                    main_code="1;32" if selected else "0",
                    glyph=glyph,
                    glyph_code="1;32" if selected else "0",
                )
                rendered_options.append(styled)
            lines.append(" / ".join(rendered_options))
        else:
            lines.append("Use ↑/↓ to move. Press Enter to confirm.")
            for idx, opt in enumerate(options):
                label = opt.get("label", opt["value"]).strip()
                selected = idx == current_index
                glyph = opt.get("selected_glyph" if selected else "unselected_glyph")
                if not glyph:
                    glyph = "●" if selected else "○"
                description = opt.get("description", "").strip() if idx == current_index else ""
                option_line = f"{glyph} {label}"
                if description:
                    option_line = f"{option_line} ({description})"
                wrapped = self._wrap_text(option_line, body_width)
                paren_depth = 0
                for line_index, chunk in enumerate(wrapped):
                    if line_index == 0:
                        rendered = chunk
                    else:
                        rendered = f"  {chunk}"
                    if selected:
                        styled, paren_depth = self._style_parenthetical_chunk(
                            rendered,
                            main_code="1;97",
                            initial_depth=paren_depth,
                            glyph=glyph if line_index == 0 else None,
                            glyph_code="1;32",
                        )
                    else:
                        styled, paren_depth = self._style_parenthetical_chunk(
                            rendered,
                            main_code="0;90",
                            paren_code="0;90",
                            initial_depth=paren_depth,
                            glyph=glyph if line_index == 0 else None,
                            glyph_code="0;90",
                        )
                    lines.append(styled)

        # Must clear exactly the *previous* frame's line count. Using len(lines) here
        # breaks when the new selection wraps to fewer lines than the old one, leaving
        # orphan rows that stack with the next prompt (duplicate headings / mangled UI).
        if previous_height > 0:
            self._clear_previous_frame(previous_height)
        for line in lines:
            self._write(line)
        return len(lines)

    def intro(self, text: str) -> None:
        for line in self._logo_frame_lines():
            self._write(line)
        if text.strip():
            self._write(self._accent(text))
            self._write("")

    def journey_rail_begin(self) -> None:
        """Start a left vertical rail (OpenClaw-style) that connects subsequent `note()` panels."""
        self._journey_rail = True
        self._journey_gap_before_next_note = False

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

    def _journey_junction_node(self, complete: bool | None) -> str:
        """Configured → green solid ◆; not configured → hollow ◇ (muted); neutral → dim ·."""
        if complete is True:
            return self._style("◆", "1;32")
        if complete is False:
            return self._muted("◇")
        return self._muted("·")

    def _note_journey_tee(self, title: str, body: str, *, complete: bool | None) -> None:
        """Spine: one continuous │ between cards (no extra │+blank that looks broken). Tee row: ◇  Title  ──┐ with spaced dashes."""
        if self._journey_gap_before_next_note:
            self._write(self._muted("│"))

        rail_prefix = self._muted("│") + "  "
        inner = max(28, min(76, self._width - 10))
        title_lines = self._wrap_text(title, max(8, inner - 4))
        body_lines: list[str] = []
        for raw_line in body.splitlines() or [body]:
            if raw_line.strip() == "":
                body_lines.append("")
            else:
                body_lines.extend(self._wrap_text(raw_line, max(8, inner - 4)))

        node = self._journey_junction_node(complete)
        title0 = self._accent(title_lines[0]) if title_lines else ""
        vis0 = self._visible_length(title0)

        cells: list[str] = []
        for ti in range(1, len(title_lines)):
            cells.append(self._accent("  " + title_lines[ti]))
        cells.append(self._muted(""))
        for bl in body_lines:
            cells.append(self._muted("  " + bl) if bl else self._muted(""))

        max_w = max((self._visible_length(c) for c in cells), default=0)
        max_w = max(max_w, vis0, 24)
        # Two spaces inside each │ … │ edge so glyphs/lines don’t crowd the border.
        inner_bar = max_w + 4
        side_pad = "  "

        m = self._muted
        n_dash = max_w - vis0
        if n_dash < 1:
            n_dash = 1
        self._write(rail_prefix + node + "  " + title0 + "  " + m("─" * n_dash) + m("┐"))
        for content in cells:
            pad = max_w - self._visible_length(content)
            padded = content + (" " * pad if pad > 0 else "")
            self._write(rail_prefix + m("│") + side_pad + padded + side_pad + m("│"))
        self._write(rail_prefix + m("└") + m("─" * inner_bar) + m("┘"))

    def note(self, title: str, body: str, *, complete: bool | None = None) -> None:
        """Closed box. Journey rail: T-pipe + junction node — green ◆ configured, hollow ◇ pending."""
        if self._journey_rail:
            self._note_journey_tee(title, body, complete=complete)
            self._journey_gap_before_next_note = True
            return

        inner = max(28, min(76, self._width - 8))

        glyph_char = ""
        if complete is True:
            glyph_char = "◆"
        elif complete is False:
            glyph_char = "◇"

        title_head = f"{glyph_char} {title}" if glyph_char else title
        title_lines = self._wrap_text(title_head, inner)

        body_lines: list[str] = []
        for raw_line in body.splitlines() or [body]:
            if raw_line.strip() == "":
                body_lines.append("")
            else:
                body_lines.extend(self._wrap_text(raw_line, max(8, inner - 2)))

        rows: list[str] = list(title_lines) + [""]
        for bl in body_lines:
            rows.append(("  " + bl) if bl else "")

        max_w = max((len(r) for r in rows), default=0)
        max_w = max(max_w, 24)
        inner_bar = max_w + 2

        top_rule = self._muted("╭" + "─" * inner_bar + "╮")
        bot_rule = self._muted("╰" + "─" * inner_bar + "╯")
        self._write(top_rule)

        title_row_count = len(title_lines)
        for idx, row in enumerate(rows):
            plain = row.ljust(max_w)
            if idx < title_row_count:
                if glyph_char and idx == 0 and plain.startswith(glyph_char):
                    after_glyph = plain[len(glyph_char) :]
                    if complete is True:
                        styled = self._style("◆", "1;32") + self._accent(after_glyph)
                    else:
                        styled = self._muted("◇") + self._accent(after_glyph)
                else:
                    styled = self._accent(plain)
            else:
                styled = self._muted(plain)
            self._write(self._muted("│") + " " + styled + " " + self._muted("│"))

        self._write(bot_rule)
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
            prev_h = 0
            while True:
                prev_h = self._render_select_frame(
                    prompt,
                    options,
                    current_index,
                    previous_height=prev_h,
                    default=default,
                    layout=layout,
                )
                key = self._read_key()
                if key in {"UP", "LEFT"}:
                    current_index = (current_index - 1) % len(options)
                elif key in {"DOWN", "RIGHT"}:
                    current_index = (current_index + 1) % len(options)
                elif key == "ENTER":
                    if prev_h > 0:
                        self._clear_previous_frame(prev_h)
                    self._write("")
                    return options[current_index]["value"]

        self._write(self._accent(prompt) if layout == "horizontal" else self._style(prompt, "1"))
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

    def _supports_inline_secret_input(self) -> bool:
        return self._is_tty and (self._key_reader is not None or self._stdin_is_tty)

    def _read_secret_key(self) -> str:
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
            if char in ("\x7f", "\b"):
                return "BACKSPACE"
            return char
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def secret(self, prompt: str, *, allow_empty: bool = False) -> str:
        suffix = " (press Enter to keep current value)" if allow_empty else ""
        rendered_prompt = f"{prompt}{suffix}: "
        styled_prompt = rendered_prompt
        if self._is_tty:
            styled_prompt, _ = self._style_parenthetical_chunk(rendered_prompt, main_code="0")
        if self._supports_inline_secret_input():
            chars: list[str] = []

            def _render() -> None:
                self._write_inline(f"\r\033[K{styled_prompt}{'*' * len(chars)}")

            _render()
            while True:
                key = self._read_secret_key()
                if key == "ENTER":
                    self._write("")
                    break
                if key == "BACKSPACE":
                    if chars:
                        chars.pop()
                        _render()
                    continue
                if len(key) != 1 or not key.isprintable():
                    continue
                chars.append(key)
                _render()
            value = "".join(chars)
            if not value and allow_empty:
                self._write(self._dim_preview("  → ********"))
            return value

        value = _prompt_secret(getpass.getpass, rendered_prompt)
        if value:
            mask = "***" + ("*" * min(len(value) - 3, 5))
            self._write(self._dim_preview(f"  → {mask}"))
        elif allow_empty:
            self._write(self._dim_preview("  → ********"))
        return value

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


_MAILBOX_ENV_KEYS = (
    "MAIL_ADDRESS",
    "IMAP_HOST",
    "IMAP_PORT",
    "IMAP_ENCRYPTION",
    "IMAP_LOGIN",
    "IMAP_PASS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_ENCRYPTION",
    "SMTP_LOGIN",
    "SMTP_PASS",
)

_LLM_ENV_KEYS = (
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_API_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_BASE_URL",
)


def _without_env_keys(dotenv: dict[str, str], keys: tuple[str, ...]) -> dict[str, str]:
    stripped = dict(dotenv)
    for key in keys:
        stripped.pop(key, None)
    return stripped


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


def _existing_config_choice(
    prompter: JourneyPrompter,
    *,
    subject: str,
    default: str,
) -> str:
    prompter.note(
        "Existing config detected",
        f"Twinbox found existing {subject} settings in the current environment. Choose whether to reuse them, update them, or reset them before continuing.",
        complete=None,
    )
    return prompter.select(
        "◆  Config handling",
        options=[
            {
                "value": "use_existing",
                "label": "Use existing values",
                "description": "Keep the detected values and continue with them.",
            },
            {
                "value": "update",
                "label": "Update values",
                "description": "Review the detected values and change what you need.",
            },
            {
                "value": "reset",
                "label": "Reset",
                "description": "Ignore the detected values and start this step from scratch.",
            },
        ],
        default=default,
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

        detect_progress = prompter.progress("Detecting mailbox settings")
        detected = detect_to_env(email, verbose=False)
        if detected is None:
            detect_progress.fail(f"Could not auto-detect mailbox servers for {email}")
            raise ValueError(f"Could not auto-detect mailbox servers for {email}")
        detect_progress.finish("Mailbox settings detected")
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
    from .llm import validate_backend

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

    # Validate the backend with a real API call
    if not dry_run:
        success, error_msg = validate_backend(backend)
        if not success:
            return (
                False,
                {
                    "prompted": True,
                    "configured": False,
                    "backend": backend.backend,
                    "model": backend.model,
                    "url": backend.url,
                    "error": error_msg,
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


def _run_with_timeout(
    func: Callable[[], tuple[bool, dict[str, Any], dict[str, str]]],
    *,
    timeout_seconds: float,
) -> tuple[bool, dict[str, Any], dict[str, str]] | None:
    result: dict[str, tuple[bool, dict[str, Any], dict[str, str]]] = {}
    error: dict[str, BaseException] = {}

    def _target() -> None:
        try:
            result["value"] = func()
        except BaseException as exc:  # pragma: no cover - forwarded to caller
            error["value"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        return None
    if "value" in error:
        raise error["value"]
    return result["value"]


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
    config_path = config_path_for_state_root(state_root)
    twinbox_config = load_twinbox_config(config_path)
    openclaw_defaults = twinbox_config.get("openclaw", {}) if isinstance(twinbox_config.get("openclaw"), dict) else {}
    integration_defaults = twinbox_config.get("integration", {}) if isinstance(twinbox_config.get("integration"), dict) else {}
    if openclaw_home is None and openclaw_defaults.get("home"):
        resolved_openclaw_home = Path(str(openclaw_defaults["home"])).expanduser()
    if openclaw_bin == "openclaw" and openclaw_defaults.get("bin"):
        openclaw_bin = str(openclaw_defaults["bin"])
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
        model_prompt = "LLM model: " if provider == "openai" else "Anthropic model: "
        model = _prompt_text(input_fn, model_prompt)
        if not model:
            report.error = "LLM model is required."
            return report
        url_prompt = "LLM API URL: " if provider == "openai" else "Anthropic base URL: "
        api_url = _prompt_text(input_fn, url_prompt)
        if not api_url:
            report.error = "LLM API URL is required."
            return report
        updates = (
            {"LLM_API_KEY": api_key, "LLM_MODEL": model, "LLM_API_URL": api_url}
            if provider == "openai"
            else {"ANTHROPIC_API_KEY": api_key, "ANTHROPIC_MODEL": model, "ANTHROPIC_BASE_URL": api_url}
        )
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

    fragment_path = Path(str(integration_defaults.get("fragment_path", ""))).expanduser() if integration_defaults.get("fragment_path") else default_openclaw_fragment_path(resolved_code_root)
    use_fragment = False
    if fragment_path.is_file():
        if fragment_decision is None:
            use_fragment = _prompt_yes_no(
                input_fn,
                f"Include OpenClaw fragment from {fragment_path}?",
                default=bool(integration_defaults.get("use_fragment", True)),
            )
        else:
            use_fragment = fragment_decision
    report.fragment = {
        "path": str(fragment_path),
        "exists": fragment_path.is_file(),
        "selected": use_fragment,
    }
    twinbox_config["integration"] = {
        "fragment_path": str(fragment_path),
        "use_fragment": bool(use_fragment),
    }
    twinbox_config["openclaw"] = {
        **openclaw_defaults,
        "home": str(resolved_openclaw_home),
        "bin": openclaw_bin,
        "strict": True,
        "sync_env_from_dotenv": True,
        "restart_gateway": True,
    }
    save_twinbox_config(config_path, twinbox_config)

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
    mailbox_apply_runner: MailboxApplyRunner = _apply_mailbox_updates,
    mailbox_validation_timeout_seconds: float = 15.0,
    llm_update_runner: LLMUpdateRunner = _apply_llm_updates,
    llm_validation_timeout_seconds: float = 15.0,
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

        config_path = config_path_for_state_root(state_root)
        twinbox_config = load_twinbox_config(config_path)
        openclaw_defaults = twinbox_config.get("openclaw", {}) if isinstance(twinbox_config.get("openclaw"), dict) else {}
        integration_defaults = twinbox_config.get("integration", {}) if isinstance(twinbox_config.get("integration"), dict) else {}
        configured_home = str(openclaw_defaults.get("home", "") or "").strip()
        resolved_openclaw_home = (openclaw_home or (Path(configured_home).expanduser() if configured_home else Path.home() / ".openclaw")).expanduser()
        if openclaw_bin == "openclaw" and openclaw_defaults.get("bin"):
            openclaw_bin = str(openclaw_defaults["bin"])
        report.code_root = str(resolved_code_root)
        report.state_root = str(state_root)
        report.openclaw_home = str(resolved_openclaw_home)
        if shutil.which(openclaw_bin) is None:
            report.error = f"Missing executable on PATH: {openclaw_bin}"
            return report

        env_file = state_root / ".env"
        dotenv = load_env_file(env_file)
        fragment_path = Path(str(integration_defaults.get("fragment_path", ""))).expanduser() if integration_defaults.get("fragment_path") else default_openclaw_fragment_path(resolved_code_root)
        fragment_exists = fragment_path.is_file()

        prompter.intro("")
        prompter.journey_rail_begin()
        prompter.note(
            "TwinBox setup",
            "Phase 1 of 2. This wizard verifies host wiring first, then hands you off to the twinbox agent for profile, materials, rules, and notifications.",
            complete=False,
        )
        prompter.note(
            "Security",
            (
                "Twinbox is personal-by-default. Please use this setup only where mailbox access, prompts, and attached tools are trusted.\n\n"
                "Shared or multi-user setups need extra lock-down before you rely on them."
            ),
            complete=False,
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
        default="cancel",
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

        prompter.note(
            "TwinBox setup",
            "Phase 1 of 2. Security check complete — host wiring steps follow.",
            complete=True,
        )
        prompter.note(
            "Security",
            (
                "You acknowledged the personal-by-default policy. "
                "Shared or multi-user hosts still need explicit lock-down beyond this wizard."
            ),
            complete=True,
        )

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
        initial_mailbox_ready = not missing_mail
        mailbox_ready = initial_mailbox_ready
        mailbox_body = (
            f"{_mailbox_summary(dotenv)}\n\n"
            "Twinbox needs mailbox access before the agent can keep onboarding."
        )
        if advanced:
            mailbox_body += f"\n\nState file: {env_file}"
        prompter.note("Mailbox", mailbox_body, complete=mailbox_ready)
        mailbox_action = "update"
        mailbox_prompt_dotenv = dotenv
        if mailbox_ready:
            mailbox_action = _existing_config_choice(
                prompter,
                subject="mailbox",
                default="use_existing" if flow == "quickstart" else "update",
            )
            if mailbox_action == "reset":
                mailbox_prompt_dotenv = _without_env_keys(dotenv, _MAILBOX_ENV_KEYS)
        mailbox_progress = None
        try:
            mailbox_updates = None
            if mailbox_action != "use_existing":
                mailbox_updates = _prompt_mailbox_customization(prompter, dotenv=mailbox_prompt_dotenv)
            mailbox_progress = prompter.progress("Checking mailbox settings")
            mailbox_result = _run_with_timeout(
                lambda: mailbox_apply_runner(
                    state_root=state_root,
                    env_file=env_file,
                    dotenv=dotenv,
                    updates=mailbox_updates,
                    dry_run=dry_run,
                ),
                timeout_seconds=mailbox_validation_timeout_seconds,
            )
            if mailbox_result is None:
                mailbox_progress.fail("Mailbox validation timed out")
                report.error = (
                    f"Mailbox validation timed out after {mailbox_validation_timeout_seconds:.1f}s."
                )
                report.mailbox = {
                    "prompted": mailbox_action != "use_existing",
                    "configured": False,
                    "missing_required": missing_required_mail_values(dotenv),
                    "status": "timeout",
                    "mail_address": (mailbox_updates or dotenv).get("MAIL_ADDRESS", ""),
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
                    "Twinbox could not finish validating the mailbox settings in time. Check the mailbox endpoint and try again.",
                    complete=None,
                )
                prompter.outro(report.error)
                return report
            mailbox_ready, report.mailbox, dotenv = mailbox_result
        except ValueError as exc:
            if mailbox_progress is not None:
                mailbox_progress.fail(str(exc))
            report.error = str(exc)
            report.mailbox = {
                "prompted": mailbox_action != "use_existing",
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
                complete=None,
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
                complete=None,
            )
            prompter.outro(report.error)
            return report
        mailbox_progress.finish("Mailbox settings validated")
        if (not initial_mailbox_ready) or (mailbox_action != "use_existing"):
            prompter.note(
                "Mailbox",
                f"{_mailbox_summary(dotenv)}\n\nMailbox settings validated for onboarding.",
                complete=True,
            )

        llm_info = _inspect_llm(env_file, dotenv)
        initial_llm_configured = bool(llm_info.get("configured"))
        llm_body = (
            f"{_llm_summary(llm_info)}\n\n"
            "Twinbox needs an LLM backend for the Phase 1-4 pipeline. Choose a provider to review or update it, or skip for now."
        )
        if llm_info.get("configured"):
            llm_body += "\nUpdate values keeps the current provider defaults available while you edit."
        prompter.note("LLM", llm_body, complete=bool(llm_info.get("configured")))
        llm_ready = bool(llm_info.get("configured"))
        llm_handling = None
        llm_prompt_dotenv = dotenv
        preserve_existing_on_skip = llm_ready
        if llm_ready:
            llm_handling = _existing_config_choice(
                prompter,
                subject="LLM",
                default="use_existing" if flow == "quickstart" else "update",
            )
            if llm_handling == "use_existing":
                report.llm = {
                    "prompted": False,
                    "configured": llm_ready,
                    "backend": llm_info.get("backend", ""),
                    "model": llm_info.get("model", ""),
                    "url": llm_info.get("url", ""),
                    "status": "configured" if llm_ready else "missing",
                }
                llm_choice = "use_existing"
            else:
                if llm_handling == "reset":
                    llm_prompt_dotenv = _without_env_keys(dotenv, _LLM_ENV_KEYS)
                    preserve_existing_on_skip = False
                llm_options: list[dict[str, str]] = [
                    {"value": "openai", "label": "Configure OpenAI", "description": "Use the OpenAI-compatible provider path."},
                    {"value": "anthropic", "label": "Configure Anthropic", "description": "Use the Anthropic native messages API path."},
                    {"value": "skip", "label": "Skip for now", "description": "Keep the current value if one exists, or leave this step incomplete for now."},
                ]
                llm_choice = prompter.select(
                    "Choose LLM setup",
                    options=llm_options,
                    default=llm_info.get("backend") or "openai",
                )
        else:
            llm_options = [
                {"value": "openai", "label": "Configure OpenAI", "description": "Use the OpenAI-compatible provider path."},
                {"value": "anthropic", "label": "Configure Anthropic", "description": "Use the Anthropic native messages API path."},
                {"value": "skip", "label": "Skip for now", "description": "Keep the current value if one exists, or leave this step incomplete for now."},
            ]
            llm_choice = prompter.select(
                "Choose LLM setup",
                options=llm_options,
                default=llm_info.get("backend") or "openai",
            )
        if llm_choice == "use_existing":
            report.llm = {
                "prompted": False,
                "configured": llm_ready,
                "backend": llm_info.get("backend", ""),
                "model": llm_info.get("model", ""),
                "url": llm_info.get("url", ""),
                "status": "configured" if llm_ready else "missing",
            }
        elif llm_choice == "skip":
            retained_llm = llm_info if preserve_existing_on_skip else {"backend": "", "model": "", "url": ""}
            llm_ready = bool(preserve_existing_on_skip and llm_info.get("configured"))
            report.llm = {
                "prompted": False,
                "configured": llm_ready,
                "backend": retained_llm.get("backend", ""),
                "model": retained_llm.get("model", ""),
                "url": retained_llm.get("url", ""),
                "status": "configured" if llm_ready else "skipped",
            }
        else:
            current_key_name, current_model_name, current_url_name = _provider_env_keys(llm_choice)
            current_key = llm_prompt_dotenv.get(current_key_name, "")
            current_model = llm_prompt_dotenv.get(current_model_name, "")
            current_url = llm_prompt_dotenv.get(current_url_name, "")
            api_url = prompter.text("API URL", default=current_url)
            api_key = prompter.secret("API key", allow_empty=bool(current_key))
            if not api_key:
                api_key = current_key
            if not api_key:
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
                    complete=None,
                )
                prompter.outro(report.error)
                return report
            model = prompter.text("Model ID", default=current_model)
            llm_progress = prompter.progress("Validating LLM configuration")
            llm_result = _run_with_timeout(
                lambda: llm_update_runner(
                    env_file=env_file,
                    dotenv=dotenv,
                    provider=llm_choice,
                    api_key=api_key,
                    model=model,
                    api_url=api_url,
                    dry_run=dry_run,
                ),
                timeout_seconds=llm_validation_timeout_seconds,
            )
            if llm_result is None:
                llm_progress.fail("LLM validation timed out")
                report.error = (
                    f"LLM validation timed out after {llm_validation_timeout_seconds:.1f}s."
                )
                report.llm = {
                    "prompted": True,
                    "configured": False,
                    "backend": llm_choice,
                    "model": model,
                    "url": api_url,
                    "error": report.error,
                }
                report.onboarding = _sync_onboarding_state(
                    state_root,
                    mailbox_ready=mailbox_ready,
                    llm_ready=False,
                    dry_run=dry_run,
                )
                prompter.note(
                    "Recovery",
                    "Twinbox could not finish validating the selected LLM provider in time. Check the endpoint and try again.",
                    complete=False,
                )
                prompter.outro(report.error)
                return report
            llm_ready, report.llm, dotenv = llm_result
            if llm_ready:
                llm_progress.finish("LLM configuration validated")
            else:
                err_detail = report.llm.get("error", "LLM validation failed")
                llm_progress.fail(err_detail)
                report.error = err_detail if isinstance(err_detail, str) else str(err_detail)
                report.onboarding = _sync_onboarding_state(
                    state_root,
                    mailbox_ready=mailbox_ready,
                    llm_ready=False,
                    dry_run=dry_run,
                )
                prompter.note(
                    "Recovery",
                    "Twinbox could not validate the LLM settings. Check API URL, key, and model id, then rerun the wizard.",
                    complete=None,
                )
                prompter.outro(report.error)
                return report

        if llm_ready and (not initial_llm_configured or llm_choice != "use_existing"):
            llm_info_final = _inspect_llm(env_file, dotenv)
            prompter.note(
                "LLM",
                f"{_llm_summary(llm_info_final)}\n\nLLM backend ready for Twinbox phases.",
                complete=True,
            )

        integration_body = (
            "This adds the small Twinbox integration config that helps OpenClaw discover Twinbox tools and stay on the recommended wiring path.\n\n"
            f"Integration fragment: {fragment_path if fragment_exists else 'not found'}"
        )
        if advanced:
            integration_body += f"\nOpenClaw home: {resolved_openclaw_home}"
        prompter.note("Twinbox tools integration", integration_body, complete=False)
        if fragment_exists:
            fragment_selected = (
                prompter.select(
                    "Use the recommended Twinbox tools integration?",
                    options=[
                        {"value": "yes", "label": "Yes (Recommended)", "selected_glyph": "●", "unselected_glyph": "○"},
                        {"value": "no", "label": "No", "selected_glyph": "●", "unselected_glyph": "○"},
                    ],
                    default="yes" if integration_defaults.get("use_fragment", True) else "no",
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
        twinbox_config["integration"] = {
            "fragment_path": str(fragment_path),
            "use_fragment": bool(fragment_selected),
        }
        twinbox_config["openclaw"] = {
            **openclaw_defaults,
            "home": str(resolved_openclaw_home),
            "bin": openclaw_bin,
            "strict": True,
            "sync_env_from_dotenv": True,
            "restart_gateway": True,
        }
        save_twinbox_config(config_path, twinbox_config)

        integration_done = (
            "Using the recommended Twinbox tools fragment."
            if fragment_selected
            else "Continuing without the bundled tools fragment."
        )
        prompter.note(
            "Twinbox tools integration",
            f"{integration_done}\n\nSaved integration choice to twinbox config.",
            complete=True,
        )

        summary_lines = [
            f"Mailbox: {report.mailbox.get('mail_address') or 'configured'}",
            f"LLM: {report.llm.get('model') or report.llm.get('backend') or report.llm.get('status', 'not configured')}",
            f"Twinbox tools integration: {'yes' if fragment_selected else 'no'}",
            f"Repo root: {resolved_code_root}",
            f"OpenClaw home: {resolved_openclaw_home}",
        ]
        if advanced:
            summary_lines.append(f"State root: {state_root}")
        prompter.note("Apply setup", "\n".join(summary_lines), complete=False)
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
                complete=None,
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
                complete=None,
            )
            prompter.outro(report.error)
            return report
        deploy_progress.finish("Host wiring applied")
        prompter.note(
            "Apply setup",
            "\n".join(summary_lines) + "\n\nOpenClaw host wiring applied.",
            complete=True,
        )

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
                complete=True,
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
            complete=False,
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
