"""
Simple selector for single/multiple selection with preview support
"""

from typing import List, NoReturn, Optional, Any
import sys

from .item import SelectorItem
from .config import SelectorConfig
from .prompt import SelectorPrompt
from ..exceptions import CancelledError

NON_INTERACTIVE_EXIT_CODE = 2
_MAX_LISTED_CANDIDATES = 50


def exit_non_interactive(message: str, candidates: Optional[List[str]] = None) -> NoReturn:
    """Cannot ask without a terminal: write guidance and candidates to stderr, then exit 2."""
    lines = [message]
    if candidates:
        lines += [f"  {i}) {c}" for i, c in enumerate(candidates[:_MAX_LISTED_CANDIDATES], 1)]
        if len(candidates) > _MAX_LISTED_CANDIDATES:
            lines.append(f"  ... and {len(candidates) - _MAX_LISTED_CANDIDATES} more")
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(NON_INTERACTIVE_EXIT_CODE)


def _exit_no_terminal(question: str, items: List[SelectorItem]) -> NoReturn:
    exit_non_interactive(
        f"[non-interactive] '{question}' needs an interactive terminal; pass the value as an argument or option. Candidates:",
        [item.label for item in items],
    )


class Selector:
    """Simple selector for single/multiple selection"""

    def __init__(self, config: Optional[SelectorConfig] = None):
        """
        Initialize selector

        Args:
            config: SelectorConfig (optional, will use defaults if not provided)
        """
        self.config = config or SelectorConfig()

    @staticmethod
    def _is_interactive_terminal() -> bool:
        """Check if running in an interactive terminal"""
        stdin = getattr(sys, "stdin", None)
        stdout = getattr(sys, "stdout", None)
        return bool(stdin and stdout and stdin.isatty() and stdout.isatty())

    def select_single(
        self,
        items: List[SelectorItem],
        message: Optional[str] = None,
        show_preview: Optional[bool] = None,
        default: Optional[Any] = None,
        raise_on_cancel: Optional[bool] = None,
        style: Optional[Any] = None,
    ) -> Optional[Any]:
        """
        Single selection

        Args:
            items: List of SelectorItem
            message: Prompt message (overrides config)
            show_preview: Whether to show preview (overrides config)
            default: Default selection value (overrides config)
            raise_on_cancel: Whether to raise exception on cancel (overrides config)

        Returns:
            Selected value or None (on cancel)

        Raises:
            KeyboardInterrupt: On Ctrl+C input
            CancelledError: On ESC cancel (if raise_on_cancel=True)
        """
        if not items:
            return None

        # Create config with overrides
        config = SelectorConfig(
            show_preview=show_preview
            if show_preview is not None
            else self.config.show_preview,
            message=message if message is not None else self.config.message,
            enable_multi_select=False,
            default=default if default is not None else self.config.default,
            raise_on_cancel=raise_on_cancel
            if raise_on_cancel is not None
            else self.config.raise_on_cancel,
            require_selection=self.config.require_selection,
            require_selection_message=self.config.require_selection_message,
            style=style,
        )

        if not self._is_interactive_terminal():
            _exit_no_terminal(config.message, items)

        try:
            prompt = SelectorPrompt(items=items, config=config)
            return prompt.run()
        except KeyboardInterrupt:
            raise
        except CancelledError:
            if config.raise_on_cancel:
                raise
            return None
        except Exception:
            if config.raise_on_cancel:
                raise
            return None

    def select_multiple(
        self,
        items: List[SelectorItem],
        message: Optional[str] = None,
        show_preview: Optional[bool] = None,
        default: Optional[List[Any]] = None,
        raise_on_cancel: Optional[bool] = None,
        style: Optional[Any] = None,
    ) -> Optional[List[Any]]:
        """
        Multiple selection

        Args:
            items: List of SelectorItem
            message: Prompt message (overrides config)
            show_preview: Whether to show preview (overrides config)
            default: Default selection value list (overrides config)
            raise_on_cancel: Whether to raise exception on cancel (overrides config)

        Returns:
            List of selected values or None (on cancel)

        Raises:
            KeyboardInterrupt: On Ctrl+C input
            CancelledError: On ESC cancel (if raise_on_cancel=True)
        """
        if not items:
            return []

        # Create config with overrides
        config = SelectorConfig(
            show_preview=show_preview
            if show_preview is not None
            else self.config.show_preview,
            message=message if message is not None else self.config.message,
            enable_multi_select=True,
            default=default if default is not None else self.config.default,
            raise_on_cancel=raise_on_cancel
            if raise_on_cancel is not None
            else self.config.raise_on_cancel,
            require_selection=self.config.require_selection,
            require_selection_message=self.config.require_selection_message,
            style=style,
        )

        if not self._is_interactive_terminal():
            _exit_no_terminal(config.message, items)

        try:
            prompt = SelectorPrompt(items=items, config=config)
            return prompt.run()
        except KeyboardInterrupt:
            raise
        except CancelledError:
            if config.raise_on_cancel:
                raise
            return None
        except Exception:
            if config.raise_on_cancel:
                raise
            return None
