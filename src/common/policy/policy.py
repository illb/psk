"""
CliPolicy — global CLI behavior policy

Usage:
    from lib.common.policy import set_policy, get_policy, CliPolicy, STRICT_POLICY
    from lib.common.policy.nav import NavigationPolicy

    set_policy(STRICT_POLICY)
    # or
    set_policy(CliPolicy(nav=NavigationPolicy(raise_on_cancel=False)))
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .nav import NavigationPolicy, DEFAULT_NAV, STRICT_NAV, SILENT_NAV
from .danger import DangerPolicy, DEFAULT_DANGER, STRICT_DANGER, SILENT_DANGER
from .permission import PermissionPolicy, OPEN_PERMISSION, READONLY_PERMISSION


@dataclass
class CliPolicy:
    """Top-level CLI behavior policy.

    Combine sub-policies here. Set globally with set_policy().
    Individual function calls can override via their own parameters.
    """
    nav:        NavigationPolicy  = field(default_factory=lambda: DEFAULT_NAV)
    danger:     DangerPolicy      = field(default_factory=lambda: DEFAULT_DANGER)
    permission: PermissionPolicy  = field(default_factory=lambda: OPEN_PERMISSION)


# ── Global state ────────────────────────────────────────────

_current_policy: CliPolicy = CliPolicy()


def set_policy(policy: CliPolicy) -> None:
    """Set the global CLI policy."""
    global _current_policy
    _current_policy = policy


def get_policy() -> CliPolicy:
    """Get the current global CLI policy."""
    return _current_policy


# ── Preset policies ──────────────────────────────────────────

DEFAULT_POLICY = CliPolicy()

STRICT_POLICY = CliPolicy(
    nav=STRICT_NAV,
    danger=STRICT_DANGER,
    permission=OPEN_PERMISSION,
)

SILENT_POLICY = CliPolicy(
    nav=SILENT_NAV,
    danger=SILENT_DANGER,
    permission=OPEN_PERMISSION,
)

READONLY_POLICY = CliPolicy(
    nav=DEFAULT_NAV,
    danger=DEFAULT_DANGER,
    permission=READONLY_PERMISSION,
)
