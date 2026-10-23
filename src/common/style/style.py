"""
Prompt style — visual configuration for prompt components

PromptStyle combines shape/layout with a PromptTheme reference.
Per-element styling uses StyledElement (text + color + bold + dim overrides).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from .theme import (
    PromptTheme,
    DEFAULT_THEME, PINK_THEME, MONO_THEME,
    SYNTHWAVE_THEME,
)


# ── StyledElement ──────────────────────────────────────────────

@dataclass
class StyledElement:
    """A UI element (character/string) with optional style overrides.

    When color/bold/dim are set, they override the theme-derived defaults.
    Use for cursor, prompt_prefix, selection markers, etc.
    """
    text: str = ""
    color: str = ""     # hex or named color; empty = use theme fallback
    bold: bool = False
    dim: bool = False

    def pt_style(self, fallback: str = "") -> str:
        """Build a prompt_toolkit style string.

        Args:
            fallback: Style/color to use when self.color is empty.
        """
        color = self.color or fallback
        parts: list[str] = []
        if self.bold:
            parts.append("bold")
        if color:
            parts.append(color)
        if self.dim:
            parts.append("dim")
        return " ".join(parts)


# ── PromptAnimationHook ────────────────────────────────────────

@runtime_checkable
class PromptAnimationHook(Protocol):
    """Protocol for prompt animation hooks.

    Reserved for future integration with cli-lib-animation.
    Implement this protocol to add per-element animations
    (blinking cursor, entry/exit effects, item transforms, etc.)
    to any prompt component.
    """

    def on_enter(self) -> None:
        """Called when the prompt appears on screen."""
        ...

    def on_exit(self, result: Any) -> None:
        """Called when the prompt exits with a result."""
        ...

    def on_cancel(self) -> None:
        """Called when the prompt is cancelled (ESC)."""
        ...

    def cursor_frame(self, text: str, t: float) -> str:
        """Transform cursor text for the current animation frame.

        Args:
            text: Original cursor character(s).
            t: Elapsed seconds since prompt appeared.
        Returns:
            Transformed cursor text (e.g. blinking via empty string alternation).
        """
        ...

    def item_frame(self, text: str, is_current: bool, t: float) -> str:
        """Transform a list item's label for the current animation frame.

        Args:
            text: Original item label.
            is_current: Whether this item is under the cursor.
            t: Elapsed seconds since prompt appeared.
        """
        ...


# ── PromptStyle ────────────────────────────────────────────────

@dataclass
class PromptStyle:
    """Visual style configuration for prompt components.

    Element fields use StyledElement for per-element color/bold/dim overrides.
    Theme-derived colors are used as fallbacks when element.color is empty.
    """

    # ── Elements ───────────────────────────────────────────────
    prompt_prefix: StyledElement = field(default_factory=StyledElement)
    cursor: StyledElement = field(default_factory=lambda: StyledElement(text="\u00bb"))   # »
    selected_marker: StyledElement = field(default_factory=lambda: StyledElement(text="\u25cf"))   # ●
    unselected_marker: StyledElement = field(default_factory=lambda: StyledElement(text="\u25cb")) # ○

    # ── Behavior ───────────────────────────────────────────────
    confirm_inline: bool = False

    # ── Key hints ──────────────────────────────────────────────
    show_key_hints: bool = True
    key_hint_sep: str = "  "

    # ── Answer summary ─────────────────────────────────────────
    show_answer_summary: bool = True
    answer_prefix: str = "\u00bb "   # »

    # ── Multiline input ────────────────────────────────────────
    multiline_bordered: bool = False
    multiline_left_bar: bool = False
    multiline_height: int = 8

    # ── List ───────────────────────────────────────────────────
    max_list_height: Optional[int] = None

    # ── Border / button ────────────────────────────────────────
    border_style: str = "square"     # "none" | "square" | "rounded"
    button_style: str = "bracket"    # "bracket" | "background"

    # ── Pager ──────────────────────────────────────────────────
    pager_line_numbers: bool = False

    # ── Theme ──────────────────────────────────────────────────
    theme: PromptTheme = field(default_factory=PromptTheme)

    # ── Animation hook (future) ────────────────────────────────
    animation: Optional[PromptAnimationHook] = None

    # ── Theme-derived color properties ─────────────────────────

    @property
    def accent(self) -> str:
        return f"bold {self.theme.primary}"

    @property
    def accent_dim(self) -> str:
        return self.theme.primary

    @property
    def dim(self) -> str:
        return self.theme.muted

    @property
    def selected(self) -> str:
        return self.theme.secondary

    @property
    def answer(self) -> str:
        return self.theme.secondary

    @property
    def placeholder(self) -> str:
        return f"fg:{self.theme.placeholder}" if self.theme.placeholder else "fg:#555555"

    # ── Per-element style properties ───────────────────────────

    @property
    def prefix_pt_style(self) -> str:
        """prompt_toolkit style string for prompt_prefix."""
        fallback = f"bold {self.theme.prefix}" if self.theme.prefix else "bold"
        return self.prompt_prefix.pt_style(fallback=fallback)

    @property
    def cursor_pt_style(self) -> str:
        """prompt_toolkit style string for cursor."""
        return self.cursor.pt_style(fallback=self.accent)

    @property
    def selected_marker_pt_style(self) -> str:
        """prompt_toolkit style string for selected marker."""
        return self.selected_marker.pt_style(fallback=f"bold {self.selected}")

    @property
    def unselected_marker_pt_style(self) -> str:
        """prompt_toolkit style string for unselected marker."""
        return self.unselected_marker.pt_style(fallback=self.dim)

    # ── Helper methods ──────────────────────────────────────────

    def prefix_fragments(self) -> list[tuple[str, str]]:
        """Return formatted text fragments for prompt_prefix (may be empty)."""
        if not self.prompt_prefix.text:
            return []
        return [(self.prefix_pt_style, self.prompt_prefix.text)]

    @property
    def border_chars(self) -> tuple[str, str, str, str, str, str]:
        """Returns (top-left, top-right, bottom-left, bottom-right, horizontal, vertical)"""
        if self.border_style == "rounded":
            return ("\u256d", "\u256e", "\u2570", "\u256f", "\u2500", "\u2502")  # ╭╮╰╯─│
        if self.border_style == "square":
            return ("\u250c", "\u2510", "\u2514", "\u2518", "\u2500", "\u2502")  # ┌┐└┘─│
        return ("", "", "", "", "", "")  # none


# ── Preset styles ──────────────────────────────────────────────

DEFAULT_STYLE = PromptStyle(
    prompt_prefix=StyledElement(text="\u276f ", bold=True),   # ❯
    cursor=StyledElement(text="\u00bb"),                       # »
    selected_marker=StyledElement(text="\u25cf"),              # ●
    unselected_marker=StyledElement(text="\u25cb"),            # ○
    theme=DEFAULT_THEME,
    border_style="square",
    button_style="bracket",
    key_hint_sep="  ",
    answer_prefix="\u00bb ",                                   # »
)

SIMPLE_STYLE = PromptStyle(
    prompt_prefix=StyledElement(text="\u2022 ", bold=True),   # •
    cursor=StyledElement(text="\u203a"),                       # ›
    selected_marker=StyledElement(text="\u25c9"),              # ◉
    unselected_marker=StyledElement(text="\u25cb"),            # ○
    confirm_inline=True,
    border_style="rounded",
    button_style="background",
    multiline_bordered=True,
    multiline_left_bar=True,
    multiline_height=6,
    max_list_height=10,
    key_hint_sep=" \u2022 ",                                   # •
    answer_prefix="> ",
    theme=PINK_THEME,
)

MINIMAL_STYLE = PromptStyle(
    prompt_prefix=StyledElement(),
    cursor=StyledElement(text="\u203a"),                       # ›
    selected_marker=StyledElement(text="\u25c9"),              # ◉
    unselected_marker=StyledElement(text="\u25cb"),            # ○
    show_key_hints=False,
    show_answer_summary=False,
    border_style="none",
    button_style="bracket",
    theme=MONO_THEME,
)

VIVID_STYLE = PromptStyle(
    prompt_prefix=StyledElement(text="\u2022 ", bold=True),   # •
    cursor=StyledElement(text=">"),
    selected_marker=StyledElement(text="\u25c6"),              # ◆
    unselected_marker=StyledElement(text="\u25c7"),            # ◇
    confirm_inline=True,
    border_style="square",
    button_style="background",
    multiline_bordered=True,
    multiline_left_bar=True,
    multiline_height=6,
    max_list_height=12,
    key_hint_sep=" \u00b7 ",                                   # ·
    answer_prefix="\u203a ",                                   # ›
    theme=SYNTHWAVE_THEME,
)

STYLES: dict[str, PromptStyle] = {
    "default": DEFAULT_STYLE,
    "simple":  SIMPLE_STYLE,
    "minimal": MINIMAL_STYLE,
    "vivid":   VIVID_STYLE,
}
