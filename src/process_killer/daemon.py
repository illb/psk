#!/usr/bin/env python3
"""
psk cleanup daemon.

Periodically runs the category killer over the always-safe categories
(zombie, orphaned LSP by default) so leaks never accumulate. Designed to be
supervised by launchd (see deploy/), but also runs
standalone. Each cycle appends one summary line to a log file.

The daemon deliberately never schedules the `gradle`, `codex`, or `claude`
categories by default — those are manual-only, to avoid any risk of killing
active build or AI sessions.
"""
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .category_killer import CategoryKiller

DEFAULT_INTERVAL_SECONDS = 1800  # 30 minutes
DEFAULT_LOG_PATH = "~/Library/Logs/psk-daemon.log"
DEFAULT_CATEGORIES = ["zombie", "lsp"]
STALE_AI_CATEGORIES = ["codex", "claude"]

_stop = False


def _handle_stop(signum, frame):
    global _stop
    _stop = True


def _log(log_path: Optional[Path], message: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} psk-daemon: {message}"
    print(line, flush=True)
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


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


def _run_cycle(
    categories: List[str],
    log_path: Optional[Path],
    check_stale_ai: bool = True,
) -> None:
    try:
        summary = CategoryKiller().kill_categories(
            categories, assume_yes=True, quiet=True)
    except Exception as e:  # a cycle must never crash the loop
        _log(log_path, f"cycle error: {e}")
        return
    by = summary.get("by_category", {})
    detail = " ".join(f"{k}={by.get(k, 0)}" for k in categories)
    _log(log_path, f"killed={summary.get('killed', 0)} targeted={summary.get('targeted', 0)} [{detail}]")
    if check_stale_ai:
        _check_stale_ai(log_path)


def run_daemon(
    categories: Optional[List[str]] = None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    log_path: Optional[str] = DEFAULT_LOG_PATH,
    check_stale_ai: bool = True,
) -> None:
    """Run the cleanup loop. `once=True` runs a single cycle and returns."""
    categories = categories or list(DEFAULT_CATEGORIES)
    resolved_log = Path(log_path).expanduser() if log_path else None

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    if once:
        _run_cycle(categories, resolved_log, check_stale_ai=check_stale_ai)
        return

    _log(resolved_log, f"started interval={interval_seconds}s categories={','.join(categories)} pid={os.getpid()}")
    while not _stop:
        _run_cycle(categories, resolved_log, check_stale_ai=check_stale_ai)
        # Sleep in short slices so SIGTERM is honored promptly.
        slept = 0
        while slept < interval_seconds and not _stop:
            time.sleep(min(5, interval_seconds - slept))
            slept += 5
    _log(resolved_log, "stopped")
    sys.exit(0)
