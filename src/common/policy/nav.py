"""
NavigationPolicy — keyboard navigation and cancel behavior
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NavigationPolicy:
    """Global navigation and cancel behavior policy.

    Controls how ESC/Ctrl+C are handled and what happens on cancel.
    """

    # Cancel behavior
    raise_on_cancel: bool = True    # ESC cancel → raise CancelledError (False = return None)

    # Exit behavior
    esc_exits: bool = True          # ESC at top level → exit (False = ignore)
    confirm_on_exit: bool = False   # Ask "are you sure?" before exiting on ESC

    # Extra cancel keys (in addition to ESC)
    extra_cancel_keys: list[str] = field(default_factory=list)


DEFAULT_NAV = NavigationPolicy()
STRICT_NAV  = NavigationPolicy(confirm_on_exit=True, raise_on_cancel=True)
SILENT_NAV  = NavigationPolicy(raise_on_cancel=False, esc_exits=False)
