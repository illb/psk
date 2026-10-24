"""
Prompt utilities — select functions copied from kcli-lib lib/common/prompt_utils.py.
"""
from typing import Optional, List, Tuple, Any

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, Window, FormattedTextControl, HSplit

from .selector import Selector, SelectorItem
from .selector.selector import exit_non_interactive
from .style import PromptStyle, PromptTheme, DEFAULT_STYLE
from .exceptions import CancelledError
from .policy import get_policy

# ── Global style state ──────────────────────────────────────

_current_style: PromptStyle = DEFAULT_STYLE


def set_style(style: PromptStyle) -> None:
    """Set the global prompt style"""
    global _current_style
    _current_style = style


def get_style() -> PromptStyle:
    """Get the current global prompt style"""
    return _current_style


def set_theme(theme: PromptTheme) -> None:
    """Set the theme on the current global style"""
    _current_style.theme = theme


def get_theme() -> PromptTheme:
    """Get the current theme"""
    return _current_style.theme


# ── Console helper ──────────────────────────────────────────

_console = None


def _get_console():
    global _console
    if _console is None:
        from rich.console import Console
        _console = Console()
    return _console


# ── Select functions ────────────────────────────────────────

def select_yes_no(
    message: str, default: bool = False, raise_on_cancel: Optional[bool] = None
) -> Optional[bool]:
    """
    Yes/No confirmation

    Args:
        message: Question message
        default: Default value (True/False)
        raise_on_cancel: Override raise-on-cancel (None = use style default)

    Returns:
        True/False or None (on cancel)
    """
    style = _current_style
    raise_on_cancel = raise_on_cancel if raise_on_cancel is not None else get_policy().nav.raise_on_cancel
    if not Selector._is_interactive_terminal():
        exit_non_interactive(
            f"[non-interactive] '{message}' needs an interactive terminal; pass --yes if the command has it."
        )
    if style.confirm_inline:
        result = _confirm_inline(message, default, style)
        if result is not None:
            _print_answer_summary(style, message, "Yes" if result else "No")
        if result is None and raise_on_cancel:
            raise CancelledError()
        return result
    return select_single(
        message=message,
        choices=[(True, "Yes"), (False, "No")],
        default=default,
        raise_on_cancel=raise_on_cancel,
    )


def select_single(
    message: str,
    choices: List[Tuple[Any, str]],
    default: Optional[Any] = None,
    raise_on_cancel: Optional[bool] = None,
) -> Optional[Any]:
    """
    Single selection (Selector-based)

    Args:
        message: Prompt message
        choices: List of (value, label) tuples
        default: Default selection value
        raise_on_cancel: Override raise-on-cancel (None = use style default)

    Returns:
        Selected value or None (on cancel)
    """
    style = _current_style
    raise_on_cancel = raise_on_cancel if raise_on_cancel is not None else get_policy().nav.raise_on_cancel
    selector_items = [
        SelectorItem(value=value, label=label)
        for value, label in choices
    ]
    selector = Selector()
    result = selector.select_single(
        items=selector_items,
        message=message,
        show_preview=False,
        default=default,
        raise_on_cancel=raise_on_cancel,
        style=style,
    )
    if result is not None:
        label = next((lbl for v, lbl in choices if v == result), str(result))
        _print_answer_summary(style, message, label)
    return result


def select_multiple(
    message: str,
    choices: List[Tuple[Any, str]],
    default: Optional[List[Any]] = None,
    raise_on_cancel: Optional[bool] = None,
) -> Optional[List[Any]]:
    """
    Multiple selection (Selector-based)

    Args:
        message: Prompt message
        choices: List of (value, label) tuples
        default: Default selection value list
        raise_on_cancel: Override raise-on-cancel (None = use style default)

    Returns:
        List of selected values or None (on cancel)
    """
    style = _current_style
    raise_on_cancel = raise_on_cancel if raise_on_cancel is not None else get_policy().nav.raise_on_cancel
    selector_items = [
        SelectorItem(value=value, label=label)
        for value, label in choices
    ]
    selector = Selector()
    result = selector.select_multiple(
        items=selector_items,
        message=message,
        show_preview=False,
        default=default,
        raise_on_cancel=raise_on_cancel,
        style=style,
    )
    if result is not None:
        labels = [next((lbl for v, lbl in choices if v == val), str(val)) for val in result]
        _print_answer_summary(style, message, ", ".join(labels))
    return result


def _key_hint_text(style: PromptStyle, hints: List[Tuple[str, str]]) -> str:
    """Build key hint line from (key, action) pairs using style separator."""
    parts = [f"{k}: {a}" for k, a in hints]
    return "  " + style.key_hint_sep.join(parts)


def _print_answer_summary(style: PromptStyle, message: str, answer: str) -> None:
    """Print one-line summary after a selection is confirmed."""
    if not style.show_answer_summary:
        return
    from rich.text import Text
    txt = Text()
    if style.prompt_prefix.text:
        txt.append(style.prompt_prefix.text, style=style.prefix_pt_style or "bold")
    txt.append(message + " ", style="bold")
    txt.append(style.answer_prefix, style=style.dim or "dim")
    txt.append(answer, style=style.answer)
    _get_console().print(txt)


def _confirm_inline(
    message: str,
    default: bool,
    style: PromptStyle,
    affirmative: str = "Yes",
    negative: str = "No",
) -> Optional[bool]:
    """Inline Yes/No toggle using left/right keys"""
    value = [default]

    kb = KeyBindings()

    @kb.add("left")
    @kb.add("h")
    def _left(event):
        value[0] = True
        event.app.invalidate()

    @kb.add("right")
    @kb.add("l")
    def _right(event):
        value[0] = False
        event.app.invalidate()

    @kb.add("y")
    @kb.add("Y")
    def _yes(event):
        event.app.exit(result=True)

    @kb.add("n")
    @kb.add("N")
    def _no(event):
        event.app.exit(result=False)

    @kb.add("enter")
    def _confirm(event):
        event.app.exit(result=value[0])

    @kb.add("escape")
    def _cancel(event):
        event.app.exit(result=None)

    @kb.add("c-c")
    def _interrupt(event):
        event.app.exit(exception=KeyboardInterrupt())

    def _render():
        fragments = []
        fragments.extend(style.prefix_fragments())
        fragments.append(("bold", f"{message}  "))
        if value[0]:
            fragments.append((f"{style.accent} reverse", f" {affirmative} "))
            fragments.append(("", "  "))
            fragments.append((style.dim, f" {negative} "))
        else:
            fragments.append((style.dim, f" {affirmative} "))
            fragments.append(("", "  "))
            fragments.append((f"{style.accent} reverse", f" {negative} "))
        return fragments

    yn_hints = [("←/→", "toggle"), ("y/n", "select"), ("enter", "confirm"), ("esc", "cancel")]
    content_window = Window(FormattedTextControl(_render, show_cursor=False), height=1, wrap_lines=False)
    if style.show_key_hints:
        hint_text = _key_hint_text(style, yn_hints)
        root = HSplit([
            content_window,
            Window(FormattedTextControl(lambda: [(style.dim, hint_text)], show_cursor=False), height=1),
        ])
    else:
        root = content_window

    app = Application(
        layout=Layout(root),
        key_bindings=kb, full_screen=False, mouse_support=False,
    )
    try:
        return app.run()
    except KeyboardInterrupt:
        raise
