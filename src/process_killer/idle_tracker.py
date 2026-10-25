#!/usr/bin/env python3
"""
Cross-cycle idle tracking for Gradle / Kotlin daemon JVMs: a CPU% snapshot cannot
tell idle from a task hand-off, so cumulative CPU time is compared between
observations. `idle_seconds` stays None until a daemon has been seen twice.
"""
import json
import os
import time
from pathlib import Path
from typing import Callable, List

from .categories import is_gradle_daemon_jvm
from .models import ProcessInfo

DEFAULT_STATE_PATH = "~/.local/state/psk/gradle-idle.json"
ACTIVE_CPU_SECONDS_PER_HOUR = 10.0
MIN_ACTIVE_CPU_SECONDS = 1.0
ACTIVE_CPU_PERCENT = 1.0
_START_TOLERANCE_SECONDS = 5


class IdleTracker:
    def __init__(self, path: str = DEFAULT_STATE_PATH, clock: Callable[[], float] = time.time):
        self.path = Path(path).expanduser()
        self.clock = clock

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, state: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def annotate(self, processes: List[ProcessInfo]) -> None:
        """Set `idle_seconds` on Gradle/Kotlin daemons and persist observations."""
        now = self.clock()
        previous = self._load()
        current = {}
        for proc in processes:
            if not is_gradle_daemon_jvm(proc):
                continue
            start = now - proc.etime_seconds
            prev = previous.get(str(proc.pid))
            same = prev is not None and abs(prev.get("start", 0) - start) <= _START_TOLERANCE_SECONDS
            since = now
            if same:
                window = max(now - prev["seen"], 1.0)
                threshold = max(MIN_ACTIVE_CPU_SECONDS, ACTIVE_CPU_SECONDS_PER_HOUR * window / 3600)
                active = (proc.cpu_time_seconds - prev["cpu"] > threshold
                          or proc.cpu >= ACTIVE_CPU_PERCENT)
                since = now if active else prev["since"]
                proc.idle_seconds = int(now - since)
            current[str(proc.pid)] = {
                "start": start, "cpu": proc.cpu_time_seconds, "seen": now, "since": since,
            }
        self._save(current)
