#!/usr/bin/env python3
"""
psk cleanup daemon.

Periodically runs the category killer over a *safe* set of categories
(zombie, orphaned LSP, idle Gradle daemons by default) so leaks never
accumulate. Designed to be supervised by launchd (see deploy/), but also runs
standalone. Each cycle appends one summary line to a log file.

The daemon deliberately never schedules the `codex` / `claude` categories —
those are manual-only, to avoid any risk of killing an active AI session.
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
DEFAULT_CATEGORIES = ["zombie", "lsp", "gradle"]

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


def _run_cycle(categories: List[str], log_path: Optional[Path]) -> None:
    try:
        summary = CategoryKiller().kill_categories(
            categories, assume_yes=True, quiet=True)
    except Exception as e:  # a cycle must never crash the loop
        _log(log_path, f"cycle error: {e}")
        return
    by = summary.get("by_category", {})
    detail = " ".join(f"{k}={by.get(k, 0)}" for k in categories)
    _log(log_path, f"killed={summary.get('killed', 0)} targeted={summary.get('targeted', 0)} [{detail}]")


def run_daemon(
    categories: Optional[List[str]] = None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    log_path: Optional[str] = DEFAULT_LOG_PATH,
) -> None:
    """Run the cleanup loop. `once=True` runs a single cycle and returns."""
    categories = categories or list(DEFAULT_CATEGORIES)
    resolved_log = Path(log_path).expanduser() if log_path else None

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    if once:
        _run_cycle(categories, resolved_log)
        return

    _log(resolved_log, f"started interval={interval_seconds}s categories={','.join(categories)} pid={os.getpid()}")
    while not _stop:
        _run_cycle(categories, resolved_log)
        # Sleep in short slices so SIGTERM is honored promptly.
        slept = 0
        while slept < interval_seconds and not _stop:
            time.sleep(min(5, interval_seconds - slept))
            slept += 5
    _log(resolved_log, "stopped")
    sys.exit(0)
