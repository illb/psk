"""Checks for rendered terminal output and for risky Console.print calls."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import rich.console
from rich.highlighter import ReprHighlighter

_CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_LEFTOVER = re.compile(r"\[[0-9;]+m")


def strip_ansi(rendered: str) -> str:
    return _CSI.sub("", rendered)


def check_ansi(rendered: str, expected_plain: str | None = None) -> list[str]:
    """Return problems found in rendered output; empty means clean.

    - every ESC starts a complete CSI sequence
    - no escape leftovers in the visible text
    - visible text equals expected_plain (highlighting must never change characters)
    """
    problems: list[str] = []
    for index, char in enumerate(rendered):
        if char == "\x1b" and not _CSI.match(rendered, index):
            problems.append(f"broken escape at {index}: {rendered[index:index + 12]!r}")
    visible = strip_ansi(rendered)
    if "\x1b" in visible or _LEFTOVER.search(visible):
        problems.append(f"escape leftovers in visible text: {visible!r}")
    if expected_plain is not None and visible.rstrip("\n") != expected_plain:
        problems.append(f"visible text changed: {visible.rstrip(chr(10))!r} != {expected_plain!r}")
    return problems


@dataclass(frozen=True)
class PrintViolation:
    kind: str
    sample: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.sample!r}"


ANSI_REPRINT = "ANSI string printed again with markup or highlight on"
REPR_HIGHLIGHT = "string printed through rich's default ReprHighlighter"


@contextmanager
def guard_console_prints() -> Iterator[list[PrintViolation]]:
    """Record risky Console.print/log calls while the block runs (works without a TTY)."""
    violations: list[PrintViolation] = []
    original_print = rich.console.Console.print
    original_log = rich.console.Console.log

    def inspect(console, objects, markup, highlight) -> None:
        highlight_on = console._highlight if highlight is None else highlight
        markup_on = console._markup if markup is None else markup
        for obj in objects:
            if not isinstance(obj, str):
                continue
            if "\x1b[" in obj and (highlight_on or markup_on):
                violations.append(PrintViolation(ANSI_REPRINT, obj[:40]))
            if highlight_on and type(console.highlighter) is ReprHighlighter:
                violations.append(PrintViolation(REPR_HIGHLIGHT, obj[:40]))

    def guarded_print(self, *objects, markup=None, highlight=None, **kwargs):
        inspect(self, objects, markup, highlight)
        return original_print(self, *objects, markup=markup, highlight=highlight, **kwargs)

    def guarded_log(self, *objects, markup=None, highlight=None, **kwargs):
        inspect(self, objects, markup, highlight)
        return original_log(self, *objects, markup=markup, highlight=highlight, **kwargs)

    rich.console.Console.print = guarded_print
    rich.console.Console.log = guarded_log
    try:
        yield violations
    finally:
        rich.console.Console.print = original_print
        rich.console.Console.log = original_log
