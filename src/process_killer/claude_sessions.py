#!/usr/bin/env python3
"""Live Claude Code sessions from ~/.claude/sessions/<pid>.json (pid, sessionId, procStart in UTC)."""
import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Set

DEFAULT_SESSIONS_DIR = "~/.claude/sessions"


def live_claude_session_ids(sessions_dir: str = DEFAULT_SESSIONS_DIR) -> Optional[Set[str]]:
    """Session ids whose recorded pid still runs the same process; None if the registry is missing."""
    root = Path(sessions_dir).expanduser()
    if not root.is_dir():
        return None
    try:
        files = list(root.glob("*.json"))
    except OSError:
        return None
    live: Set[str] = set()
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        pid, session_id = data.get("pid"), data.get("sessionId")
        if isinstance(pid, int) and isinstance(session_id, str) and _same_process(pid, data.get("procStart")):
            live.add(session_id)
    return live


def _same_process(pid: int, proc_start) -> bool:
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
            timeout=5, env={**os.environ, "TZ": "UTC"},
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return True  # unverifiable -> keep the session live so its processes are spared
    if not out:
        return False
    return not proc_start or " ".join(out.split()) == " ".join(str(proc_start).split())
