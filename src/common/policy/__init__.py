"""
CLI behavior policy system
"""
from .nav import NavigationPolicy, DEFAULT_NAV, STRICT_NAV, SILENT_NAV
from .danger import (
    DangerPolicy, DangerLevel,
    DEFAULT_DANGER, STRICT_DANGER, SILENT_DANGER,
    confirm_dangerous, http_danger_level,
)
from .permission import (
    PermissionPolicy,
    OPEN_PERMISSION, READONLY_PERMISSION, ASK_WRITE_PERMISSION, ASK_ONCE_PERMISSION,
    check_permission, clear_ask_cache,
)
from .policy import (
    CliPolicy, set_policy, get_policy,
    DEFAULT_POLICY, STRICT_POLICY, SILENT_POLICY, READONLY_POLICY,
)

__all__ = [
    # Navigation
    "NavigationPolicy",
    "DEFAULT_NAV",
    "STRICT_NAV",
    "SILENT_NAV",
    # Danger
    "DangerPolicy",
    "DangerLevel",
    "DEFAULT_DANGER",
    "STRICT_DANGER",
    "SILENT_DANGER",
    "confirm_dangerous",
    "http_danger_level",
    # Permission
    "PermissionPolicy",
    "OPEN_PERMISSION",
    "READONLY_PERMISSION",
    "ASK_WRITE_PERMISSION",
    "ASK_ONCE_PERMISSION",
    "check_permission",
    "clear_ask_cache",
    # Top-level
    "CliPolicy",
    "set_policy",
    "get_policy",
    # Presets
    "DEFAULT_POLICY",
    "STRICT_POLICY",
    "SILENT_POLICY",
    "READONLY_POLICY",
]
