"""
PermissionPolicy — operation access control policy

Controls whether an operation is allowed at all.
Different from DangerPolicy (which controls confirmation);
PermissionPolicy controls access — "can this be done?".

Usage:
    from lib.common.policy.permission import check_permission, PermissionPolicy
    from lib.common.policy.danger import DangerLevel

    # Returns True = allowed, False = denied, raises UnauthorizedError on "deny" mode
    if not check_permission("write config", DangerLevel.WRITE):
        return
"""
from __future__ import annotations

from dataclasses import dataclass

from .danger import DangerLevel


# ── Session-level ask cache ───────────────────────────────────
# Cleared on process restart. Stores approved levels when ask_once=True.
_ask_cache: set[str] = set()


def clear_ask_cache() -> None:
    """Clear the session permission cache (useful for testing)."""
    _ask_cache.clear()


# ── PermissionPolicy ──────────────────────────────────────────

@dataclass
class PermissionPolicy:
    """Access control policy — what operations are permitted.

    Combine with DangerPolicy for full safety coverage:
      PermissionPolicy → can this operation run at all?
      DangerPolicy     → should the user confirm before running?
    """

    # Level-based allow flags
    allow_read:   bool = True   # READ operations always allowed by default
    allow_write:  bool = True   # WRITE operations allowed by default
    allow_danger: bool = True   # DANGER operations allowed by default

    # Behavior when an operation is not allowed
    on_unauthorized: str = "deny"  # "deny" | "ask" | "allow"
    #   deny  → raise UnauthorizedError immediately
    #   ask   → prompt user for one-time approval
    #   allow → pass through (policy effectively disabled)

    # ask mode options
    ask_once: bool = False   # cache approval per level for the session


OPEN_PERMISSION       = PermissionPolicy()  # all allowed (default)
READONLY_PERMISSION   = PermissionPolicy(allow_write=False, allow_danger=False, on_unauthorized="deny")
ASK_WRITE_PERMISSION  = PermissionPolicy(allow_write=False, allow_danger=False, on_unauthorized="ask")
ASK_ONCE_PERMISSION   = PermissionPolicy(allow_write=False, allow_danger=False, on_unauthorized="ask", ask_once=True)


# ── check_permission ──────────────────────────────────────────

def _is_allowed(policy: PermissionPolicy, level: str) -> bool:
    if level == DangerLevel.READ:
        return policy.allow_read
    if level == DangerLevel.WRITE:
        return policy.allow_write
    if level == DangerLevel.DANGER:
        return policy.allow_danger
    return False


def check_permission(
    action: str,
    level: str = DangerLevel.READ,
) -> bool:
    """Check if an operation is permitted by the current policy.

    Args:
        action: Human-readable description of the operation
        level:  DangerLevel constant (READ / WRITE / DANGER)

    Returns:
        True  → operation is permitted
        False → operation is denied (on_unauthorized="ask" and user declined)

    Raises:
        UnauthorizedError: when on_unauthorized="deny" and level is not allowed
        KeyboardInterrupt: on Ctrl+C during ask prompt
    """
    from .policy import get_policy
    from ..exceptions import UnauthorizedError

    policy = get_policy().permission

    # Already allowed by policy
    if _is_allowed(policy, level):
        return True

    # on_unauthorized="allow" → pass through regardless
    if policy.on_unauthorized == "allow":
        return True

    # on_unauthorized="deny" → raise immediately
    if policy.on_unauthorized == "deny":
        raise UnauthorizedError(action, level)

    # on_unauthorized="ask" → prompt user
    if policy.ask_once and level in _ask_cache:
        return True

    try:
        from ..prompt_utils import select_yes_no
        result = select_yes_no(
            f"Allow '{action}' ({level} operation)?",
            default=False,
            raise_on_cancel=False,
        )
        if result and policy.ask_once:
            _ask_cache.add(level)
        return bool(result)
    except KeyboardInterrupt:
        raise
    except Exception:
        return False
