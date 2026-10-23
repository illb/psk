"""
DangerPolicy — dangerous operation confirmation policy

Usage:
    from lib.common.policy.danger import confirm_dangerous, DangerLevel, http_danger_level

    # Decorator-free usage — call before executing
    if not confirm_dangerous("delete", target, level=DangerLevel.DANGER, force=force):
        return
"""
from __future__ import annotations

import sys
from dataclasses import dataclass


# ── Danger level ─────────────────────────────────────────────

class DangerLevel:
    READ   = "read"    # query, list — always allowed
    WRITE  = "write"   # create, update — requires confirmation
    DANGER = "danger"  # delete, irreversible — requires strong confirmation


# ── HTTP method → danger level ────────────────────────────────

HTTP_METHOD_LEVEL: dict[str, str] = {
    "GET":     DangerLevel.READ,
    "HEAD":    DangerLevel.READ,
    "OPTIONS": DangerLevel.READ,
    "POST":    DangerLevel.WRITE,
    "PUT":     DangerLevel.WRITE,
    "PATCH":   DangerLevel.WRITE,
    "DELETE":  DangerLevel.DANGER,
}


def http_danger_level(method: str) -> str:
    """Return DangerLevel for an HTTP method."""
    return HTTP_METHOD_LEVEL.get(method.upper(), DangerLevel.WRITE)


# ── DangerPolicy ─────────────────────────────────────────────

@dataclass
class DangerPolicy:
    """Confirmation policy for dangerous operations."""

    # Confirmation required per level
    confirm_write:  bool = True
    confirm_danger: bool = True

    # Non-interactive mode: "block" | "allow"
    non_interactive_write:  str = "block"
    non_interactive_danger: str = "block"

    # --force / --yes flag behavior
    force_skips_write:  bool = True   # --force skips WRITE confirmation
    force_skips_danger: bool = True   # --force skips DANGER confirmation

    # Prompt messages
    write_prompt:  str = "This operation will make changes. Proceed?"
    danger_prompt: str = "⚠️  This operation cannot be undone. Are you sure?"


DEFAULT_DANGER = DangerPolicy()
STRICT_DANGER  = DangerPolicy(
    force_skips_write=False,
    force_skips_danger=False,
)
SILENT_DANGER  = DangerPolicy(
    confirm_write=False,
    confirm_danger=False,
    non_interactive_write="allow",
    non_interactive_danger="allow",
)


# ── confirm_dangerous ─────────────────────────────────────────

def confirm_dangerous(
    action: str,
    target: str,
    level: str = DangerLevel.WRITE,
    force: bool = False,
) -> bool:
    """Check if a dangerous operation should proceed.

    Args:
        action: Operation description (e.g. "delete", "update")
        target: Target of the operation (e.g. resource name, file path)
        level:  DangerLevel constant
        force:  Whether --force / --yes flag was passed

    Returns:
        True  → proceed
        False → cancelled or blocked
    """
    from .policy import get_policy

    policy = get_policy().danger

    # READ always passes
    if level == DangerLevel.READ:
        return True

    # --force skips confirmation per level
    if force:
        if level == DangerLevel.WRITE  and policy.force_skips_write:
            return True
        if level == DangerLevel.DANGER and policy.force_skips_danger:
            return True

    # Non-interactive mode
    if not sys.stdin.isatty():
        ni = (
            policy.non_interactive_danger
            if level == DangerLevel.DANGER
            else policy.non_interactive_write
        )
        if ni == "allow":
            return True
        # block
        print(
            f"[danger] '{action}' on '{target}' requires interactive mode or --force.",
            file=sys.stderr,
        )
        return False

    # Policy says skip confirmation for this level
    if level == DangerLevel.WRITE  and not policy.confirm_write:
        return True
    if level == DangerLevel.DANGER and not policy.confirm_danger:
        return True

    # Interactive confirmation prompt
    prompt_msg = policy.danger_prompt if level == DangerLevel.DANGER else policy.write_prompt
    msg = f"{prompt_msg}\n  {action}: {target}"

    try:
        # Circular import guard: prompt_utils imports policy, policy imports prompt_utils here
        from ..prompt_utils import select_yes_no
        result = select_yes_no(msg, default=False, raise_on_cancel=False)
        return bool(result)
    except KeyboardInterrupt:
        raise
    except Exception:
        return False
