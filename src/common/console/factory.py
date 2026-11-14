"""The only place that constructs rich Console objects."""

from __future__ import annotations

from typing import IO, Literal

from rich.console import Console
from rich.highlighter import Highlighter
from rich.text import Text
from rich.theme import Theme

from .highlight import DataHighlighter, MinimalHighlighter

HighlightMode = Literal["basic", "minimal", "data"]
HIGHLIGHT_MODES: tuple[HighlightMode, ...] = ("basic", "minimal", "data")

THEME = Theme(
    {
        "ok": "green",
        "warn": "yellow",
        "err": "red",
        "muted": "dim",
        "value": "underline",
        "path": "cyan",
        "key": "bold",
        "data.key": "bold",
        "data.value": "cyan",
        "data.url": "underline",
    }
)


def _highlighter(mode: HighlightMode) -> Highlighter:
    return MinimalHighlighter() if mode == "minimal" else DataHighlighter()


def make_console(
    *,
    mode: HighlightMode = "basic",
    stderr: bool = False,
    file: IO[str] | None = None,
    force_terminal: bool | None = None,
    width: int | None = None,
) -> Console:
    """Build a console. Auto-highlight runs only in "minimal" and "data" modes.

    The theme is always loaded so callers can mark values by meaning ([ok], [value], [path]).
    NO_COLOR and TTY detection are left to rich; force_terminal is for buffer rendering only.
    """
    if mode not in HIGHLIGHT_MODES:
        raise ValueError(f"unknown highlight mode: {mode}")
    return Console(
        stderr=stderr,
        file=file,
        force_terminal=force_terminal,
        width=width,
        theme=THEME,
        highlight=mode in ("minimal", "data"),
        highlighter=_highlighter(mode),
    )


def print_ansi(console: Console, rendered: str, **kwargs) -> None:
    """Print a string that already carries ANSI codes without re-highlighting it."""
    console.print(Text.from_ansi(rendered), **kwargs)


def styled(text: str, style: str) -> Text:
    return Text(text, style=style)
