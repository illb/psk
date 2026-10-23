"""
Prompt wrappers kept for existing callers — backed by the standard selector (common.prompt_utils).
"""
from typing import Optional, List, Any

from .prompt_utils import select_single as _select_single, select_yes_no as _select_yes_no
from .selector import Selector, SelectorConfig, SelectorItem


def select_yes_no(
    message: str,
    default: bool = False,
    raise_on_cancel: bool = True
) -> Optional[bool]:
    """Yes/No question. None when non-interactive, or on ESC unless raise_on_cancel (then CancelledError)."""
    return _select_yes_no(message, default=default, raise_on_cancel=raise_on_cancel)


def select_single(
    title: str,
    choices: List[tuple],
    default: Optional[Any] = None
) -> Optional[Any]:
    """Single selection from (value, label) tuples. CancelledError on ESC, None when non-interactive."""
    return _select_single(title, choices, default=default, raise_on_cancel=True)


def select_checkbox(
    title: str,
    choices: List[tuple],
    checked_values: Optional[List[Any]] = None,
) -> List[Any]:
    """Multi-selection from (value, label) tuples; may be empty. CancelledError on ESC."""
    selector = Selector(SelectorConfig(require_selection=False, raise_on_cancel=True))
    selected = selector.select_multiple(
        items=[SelectorItem(value=value, label=label) for value, label in choices],
        message=title,
        default=list(checked_values or []),
    )
    return selected or []
