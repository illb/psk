#!/usr/bin/env python3
"""
Kill category definitions.

Each category bundles a human label with a predicate that decides whether a
given process belongs to it. The `kill` command matches processes against the
selected categories and terminates the union.

Strategies:
- "terminate": signal the matched pid directly (SIGTERM -> SIGKILL).
- "reap_parent": the matched pid is a zombie and cannot be signalled; nudge its
  parent with SIGCHLD so the parent reaps it.
"""
from dataclasses import dataclass
import shlex
from typing import Callable, List, Optional

from .models import ProcessInfo
from .tail_output import disconnected_tail_identity

# Command substrings that identify a language server process (case-insensitive).
_LSP_MARKERS = (
    "language_servers",          # serena: ~/.serena/language_servers/...
    "language-server",           # typescript-language-server, etc.
    "languageserver",            # KotlinLanguageServer
    "langserver",                # pyright-langserver
    "rust-analyzer",
    "gopls",
    "jdtls",
    "pylsp",
    "pyright",
)

# Java main classes that identify Gradle / Kotlin daemon processes.
_GRADLE_DAEMON_MARKERS = (
    "org.gradle.launcher.daemon.bootstrap.gradledaemon",
    "org.jetbrains.kotlin.daemon.kotlincompiledaemon",
)

# CPU% below this counts as "idle" for daemon categories.
_IDLE_CPU = 1.0

# A codex/claude process is only a cleanup target if orphaned (PPID 1) or this
# old — never a recent, actively-driven session.
STALE_SECONDS = 3 * 86400  # 3 days

# Command substrings that identify an OpenAI Codex CLI process.
_CODEX_MARKERS = (
    "@openai/codex",
    "codex-darwin",
    "/bin/codex",
    "codex resume",
    "codex.app",
)

def _is_zombie(proc: ProcessInfo) -> bool:
    return "Z" in (proc.stat or "")


def _is_orphan_or_stale(proc: ProcessInfo) -> bool:
    return proc.ppid == "1" or proc.etime_seconds >= STALE_SECONDS


def _orphan_or_stale_reason(proc: ProcessInfo) -> str:
    reasons = []
    if proc.ppid == "1":
        reasons.append("orphaned: PPID 1")
    if proc.etime_seconds >= STALE_SECONDS:
        reasons.append("stale: >= 3 days")
    return "; ".join(reasons)


def _is_codex_leak(proc: ProcessInfo) -> bool:
    if _is_zombie(proc):
        return False
    command = (proc.command or "").lower()
    if not any(marker in command for marker in _CODEX_MARKERS):
        return False
    return _is_orphan_or_stale(proc)


def _is_claude_leak(proc: ProcessInfo) -> bool:
    if _is_zombie(proc):
        return False
    # Match the claude CLI by executable name, not by any path that merely
    # contains "claude" (e.g. ~/.claude/skills/...): check the command's first
    # token basename, plus the explicit "claude-code" marker.
    command = (proc.command or "").lower()
    first = command.split()[0] if command.split() else ""
    base = first.rsplit("/", 1)[-1]
    is_claude_cli = base == "claude" or base.startswith("claude ") or "claude-code" in command
    if not is_claude_cli:
        return False
    return _is_orphan_or_stale(proc)


def _is_orphan_lsp(proc: ProcessInfo) -> bool:
    if _is_zombie(proc):
        return False
    if proc.ppid != "1":
        return False
    command = (proc.command or "").lower()
    return any(marker in command for marker in _LSP_MARKERS)


def _tail_follows(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens or tokens[0].rsplit("/", 1)[-1] != "tail":
        return False

    following = False
    args = iter(tokens[1:])
    for token in args:
        # ps command strings may lose argument boundaries. Never scan filenames
        # for options; ambiguous or unsupported syntax stays out of the targets.
        if token == "--" or token == "-" or not token.startswith("-"):
            break
        if token in {"--follow", "--follow=name", "--follow=descriptor"}:
            following = True
        elif token in {"--quiet", "--silent", "--verbose", "--retry"}:
            continue
        elif token in {"--lines", "--bytes"}:
            if not next(args, "").lstrip("+-").isdigit():
                return False
        elif token.startswith(("--lines=", "--bytes=")):
            if not token.partition("=")[2].lstrip("+-").isdigit():
                return False
        elif token.startswith("--"):
            return False
        else:
            for index, flag in enumerate(token[1:], start=1):
                if flag in "fF":
                    following = True
                elif flag in "qv":
                    continue
                elif flag in "ncb":
                    count = token[index + 1:] or next(args, "")
                    if not count.lstrip("+-").isdigit():
                        return False
                    break
                else:
                    return False
    return following


def _is_orphan_tail(proc: ProcessInfo) -> bool:
    if _is_zombie(proc):
        return False
    if proc.ppid != "1":
        return False
    if not _tail_follows(proc.command or ""):
        return False
    identity = disconnected_tail_identity(proc.pid)
    if identity is None:
        return False
    if proc.tail_identity is not None and proc.tail_identity != identity:
        return False
    proc.tail_identity = identity
    return True


def _is_idle_gradle(proc: ProcessInfo) -> bool:
    if _is_zombie(proc):
        return False
    if proc.cpu >= _IDLE_CPU:
        return False
    command = (proc.command or "").lower()
    first = command.split()[0] if command.split() else ""
    base = first.rsplit("/", 1)[-1]
    if base not in {"java", "java.exe"}:
        return False
    return any(marker in command for marker in _GRADLE_DAEMON_MARKERS)


@dataclass(frozen=True)
class KillCategory:
    """A selectable group of processes to terminate."""
    key: str
    label: str
    description: str
    strategy: str                         # "terminate" | "reap_parent"
    matcher: Callable[[ProcessInfo], bool]
    reason: Optional[Callable[[ProcessInfo], str]] = None


CATEGORIES: List[KillCategory] = [
    KillCategory(
        key="zombie",
        label="Zombie processes",
        description="Defunct processes (stat Z). Cannot be killed directly; "
                    "their parent is nudged (SIGCHLD) to reap them.",
        strategy="reap_parent",
        matcher=_is_zombie,
    ),
    KillCategory(
        key="lsp",
        label="Orphaned language servers (PPID 1)",
        description="Leaked LSP processes (serena / pyright / typescript / kotlin ...) "
                    "reparented to launchd after their session died.",
        strategy="terminate",
        matcher=_is_orphan_lsp,
    ),
    KillCategory(
        key="orphan-tail",
        label="Disconnected orphaned log followers",
        description="PPID 1 tail followers with a kernel-verified disconnected "
                    "stdout pipe. Live readers and unverified outputs are protected.",
        strategy="terminate",
        matcher=_is_orphan_tail,
        reason=lambda proc: "PPID 1; stdout pipe has no peer and is at EOF",
    ),
    KillCategory(
        key="gradle",
        label="Idle Gradle/Kotlin daemons",
        description="Gradle / Kotlin daemon JVMs sitting idle (CPU < 1%). "
                    "Manual cleanup only because active builds can briefly look idle.",
        strategy="terminate",
        matcher=_is_idle_gradle,
    ),
    KillCategory(
        key="codex",
        label="Orphaned / stale codex",
        description="OpenAI Codex CLI processes that are orphaned (PPID 1) or "
                    "older than 3 days. Active recent sessions are never matched.",
        strategy="terminate",
        matcher=_is_codex_leak,
        reason=_orphan_or_stale_reason,
    ),
    KillCategory(
        key="claude",
        label="Orphaned / stale claude",
        description="Claude Code CLI processes that are orphaned (PPID 1) or "
                    "older than 3 days. Active recent sessions are never matched.",
        strategy="terminate",
        matcher=_is_claude_leak,
        reason=_orphan_or_stale_reason,
    ),
]

CATEGORY_BY_KEY = {category.key: category for category in CATEGORIES}


def category_keys() -> List[str]:
    return [category.key for category in CATEGORIES]
