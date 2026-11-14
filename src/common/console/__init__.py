"""Rich console factory, explicit highlighting and ANSI output checks (copy of kcli-lib lib.common.console)."""

from .checks import (
    ANSI_REPRINT,
    REPR_HIGHLIGHT,
    PrintViolation,
    check_ansi,
    guard_console_prints,
    strip_ansi,
)
from .factory import (
    HIGHLIGHT_MODES,
    THEME,
    HighlightMode,
    make_console,
    print_ansi,
    styled,
)
from .highlight import DataHighlighter, MinimalHighlighter

__all__ = [
    "ANSI_REPRINT",
    "HIGHLIGHT_MODES",
    "REPR_HIGHLIGHT",
    "THEME",
    "DataHighlighter",
    "HighlightMode",
    "MinimalHighlighter",
    "PrintViolation",
    "check_ansi",
    "guard_console_prints",
    "make_console",
    "print_ansi",
    "strip_ansi",
    "styled",
]
