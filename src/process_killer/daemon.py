#!/usr/bin/env python3
"""
psk cleanup daemon.

Periodically runs the category killer over the default categories
(zombie, orphaned LSP, oversized idle serena language servers, verified
disconnected log followers and Gradle/Kotlin daemons idle 1h+ across cycles) so
leaks never accumulate. Designed to be supervised by launchd (see deploy/), but also runs
standalone. Each cycle appends one summary line to a log file.

The daemon deliberately never schedules the snapshot-based `gradle`, `codex`,
or `claude` categories by default — those are manual-only, to avoid any risk of
killing active build or AI sessions.
"""
import os
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .category_killer import CategoryKiller
from .hooks import DEFAULT_HOOKS_PATH, HookRunner, load_hooks
from .idle_tracker import IdleTracker

DEFAULT_INTERVAL_SECONDS = 1800  # 30 minutes
DEFAULT_LOG_PATH = "~/Library/Logs/psk-daemon.log"
DEFAULT_CATEGORIES = [
    "zombie", "lsp", "lsp-oversize", "orphan-tail", "gradle-idle", "gradle-stuck", "kotlin-idle",
    "scratchpad-orphan",
]
STALE_AI_CATEGORIES = ["codex", "claude"]

_stop = False


def _handle_stop(signum, frame):
    global _stop
    _stop = True


def _log(log_path: Optional[Path], message: str, *, required: bool = False) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} psk-daemon: {message}"
    print(line, flush=True)
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as error:
        if required:
            # Do not let per-process OSError handlers mistake this for kill failure.
            raise RuntimeError("audit log write failed") from error
        print("psk-daemon: log file write failed", file=sys.stderr, flush=True)


def _format_stale_ai_targets(targets) -> str:
    details = []
    for proc, category in targets:
        reason = category.reason(proc) if category.reason else "matched"
        details.append(f"{category.key}:{proc.pid}({reason})")
    return " ".join(details)


def _check_stale_ai(log_path: Optional[Path]) -> None:
    try:
        targets = CategoryKiller().find_category_targets(STALE_AI_CATEGORIES)
    except Exception as e:
        _log(log_path, f"stale-ai check error: {e}")
        return
    if not targets:
        return
    detail = _format_stale_ai_targets(targets)
    _log(log_path, f"stale-ai detected={len(targets)} {detail} review='psk stale-ai'")


def _auditor(log_path: Optional[Path], cycle_id: str, counts: Optional[dict] = None):
    def audit(event):
        _log(log_path, "audit " + json.dumps(
            {**event, "cycle_id": cycle_id, "actor_pid": os.getpid()},
            ensure_ascii=True, sort_keys=True), required=True)
        if counts is not None and event.get("event") == "signal" and event.get("outcome") in counts:
            counts[event["outcome"]] += 1
    return audit


def _report_hook_kills(log_path: Optional[Path], killed: List[dict]) -> None:
    if killed:
        detail = " ".join(f"{k['category']}:{k['pid']}" for k in killed)
        _log(log_path, f"hook killed={len(killed)} {detail}")


def _run_hooks(runner: Optional[HookRunner], log_path: Optional[Path], killed: Optional[List[dict]] = None) -> None:
    if runner is None:
        return
    runner.audit = _auditor(log_path, f"{os.getpid()}-hook-{time.time_ns()}")
    try:
        extra = runner.post_kill(killed) if killed is not None else runner.tick()
    except Exception as e:  # a hook must never crash the loop
        _log(log_path, f"hook error: type={type(e).__name__}")
        return
    _report_hook_kills(log_path, extra)


def _run_cycle(
    categories: List[str],
    log_path: Optional[Path],
    check_stale_ai: bool = True,
    hook_runner: Optional[HookRunner] = None,
) -> None:
    cycle_id = f"{os.getpid()}-{time.time_ns()}"
    counts = {"attempt": 0, "sent": 0, "error": 0}
    audit = _auditor(log_path, cycle_id, counts)

    try:
        audit({"event": "cycle-start", "categories": categories})
        killer = CategoryKiller(audit=audit, idle_tracker=IdleTracker())
        summary = killer.kill_categories(
            categories, assume_yes=True, quiet=True)
        audit({"event": "cycle-end", "status": "complete", "summary": summary,
               "signals": counts.copy()})
    except Exception as e:  # a cycle must never crash the loop
        _log(log_path, f"cycle error: cycle_id={cycle_id} type={type(e).__name__}")
        return
    by = summary.get("by_category", {})
    detail = " ".join(f"{k}={by.get(k, 0)}" for k in categories)
    _log(log_path, f"killed={summary.get('killed', 0)} targeted={summary.get('targeted', 0)} "
         f"reap_signals={summary.get('reap_signals', 0)} [{detail}]")
    if summary.get("killed_pids"):
        _run_hooks(hook_runner, log_path, summary["killed_pids"])
    if check_stale_ai:
        _check_stale_ai(log_path)


def run_daemon(
    categories: Optional[List[str]] = None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    log_path: Optional[str] = DEFAULT_LOG_PATH,
    check_stale_ai: bool = True,
    hooks_path: Optional[str] = DEFAULT_HOOKS_PATH,
) -> None:
    """Run the cleanup loop. `once=True` runs a single cycle and returns."""
    categories = categories or list(DEFAULT_CATEGORIES)
    resolved_log = Path(log_path).expanduser() if log_path else None
    try:
        hooks = load_hooks(hooks_path)
    except (OSError, ValueError, KeyError, TypeError) as e:
        _log(resolved_log, f"hooks config error: type={type(e).__name__} — running without hooks")
        hooks = []
    hook_runner = HookRunner(hooks, audit=lambda event: None) if hooks else None

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    if once:
        _run_cycle(categories, resolved_log, check_stale_ai=check_stale_ai, hook_runner=hook_runner)
        _run_hooks(hook_runner, resolved_log)
        return

    hook_names = ",".join(h.name for h in hooks) or "-"
    _log(resolved_log, f"started interval={interval_seconds}s categories={','.join(categories)} "
         f"hooks={hook_names} pid={os.getpid()}")
    while not _stop:
        _run_cycle(categories, resolved_log, check_stale_ai=check_stale_ai, hook_runner=hook_runner)
        # Sleep in short slices so SIGTERM is honored promptly; hooks run on their own interval.
        slept = 0
        while slept < interval_seconds and not _stop:
            _run_hooks(hook_runner, resolved_log)
            time.sleep(min(5, interval_seconds - slept))
            slept += 5
    _log(resolved_log, "stopped")
    sys.exit(0)
