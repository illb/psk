"""psk hook: a shared Gradle lock held by a build that stopped making progress while others wait.

tick: picks the build's gradle client (the daemon cancels the build, the lock holder exits, the lock frees).
post-kill: when a killed process belonged to a holder's build and the holder still holds the lock, picks the
holder and its remaining descendants. Lock files are never removed.
"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

DEFAULT_LOCK = "/tmp/as-incubator-gradle.lock"
_CLIENT_MARKERS = ("org.gradle.wrapper.GradleWrapperMain", "org.gradle.launcher.GradleMain")
_STATE_FILE = "gradle-lock-stall.json"


@dataclass(frozen=True)
class Proc:
    pid: int
    ppid: int
    etime: int
    cpu: float
    stat: str
    command: str


def _duration(value: str) -> float:
    days, _, rest = value.rpartition("-")
    total = 0.0
    for part in rest.split(":"):
        try:
            total = total * 60 + float(part)
        except ValueError:
            return 0.0
    return total + (int(days) * 86400 if days.isdigit() else 0)


def snapshot() -> Dict[int, Proc]:
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,time=,stat=,command="],
                         capture_output=True, text=True, timeout=10).stdout
    procs = {}
    for line in out.splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6 and fields[0].isdigit():
            procs[int(fields[0])] = Proc(int(fields[0]), int(fields[1]), int(_duration(fields[2])),
                                         _duration(fields[3]), fields[4], fields[5])
    return procs


def lock_fds(lock: str) -> Set[int]:
    """PIDs with the lock file open on its current inode."""
    try:
        inode = os.stat(lock).st_ino
    except OSError:
        return set()
    out = subprocess.run(["lsof", "-F", "pi", "--", lock], capture_output=True, text=True,
                         timeout=10).stdout
    pids, pid = set(), None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("i") and pid is not None and line[1:] == str(inode):
            pids.add(pid)
    return pids


def daemon_of(client: int) -> Optional[int]:
    """The daemon the client talks to: the local listener on the far end of its TCP connection."""
    out = subprocess.run(["lsof", "-a", "-p", str(client), "-iTCP", "-sTCP:ESTABLISHED", "-Fn", "-P"],
                         capture_output=True, text=True, timeout=10).stdout
    for line in out.splitlines():
        match = re.match(r"n127\.0\.0\.1:\d+->127\.0\.0\.1:(\d+)$", line)
        if not match:
            continue
        listener = subprocess.run(["lsof", "-t", f"-iTCP:{match.group(1)}", "-sTCP:LISTEN"],
                                  capture_output=True, text=True, timeout=10).stdout.split()
        if listener and listener[0].isdigit() and int(listener[0]) != client:
            return int(listener[0])
    return None


def _children(procs: Dict[int, Proc]) -> Dict[int, List[int]]:
    children: Dict[int, List[int]] = {}
    for proc in procs.values():
        children.setdefault(proc.ppid, []).append(proc.pid)
    return children


def _descendants(pid: int, children: Dict[int, List[int]]) -> List[int]:
    found, queue = [], list(children.get(pid, []))
    while queue:
        child = queue.pop()
        found.append(child)
        queue.extend(children.get(child, []))
    return found


def _live(pid: int, procs: Dict[int, Proc]) -> bool:
    return pid in procs and not procs[pid].stat.startswith("Z")


@dataclass
class Holding:
    lock: str
    holder: int
    waiters: int
    client: Optional[int]
    daemon: Optional[int]
    build: List[int]


def holdings(lock: str, procs: Dict[int, Proc], find_daemon=daemon_of) -> List[Holding]:
    children = _children(procs)
    fds = lock_fds(lock)
    holders = [pid for pid in fds if any(_live(c, procs) for c in children.get(pid, []))]
    blocked = [p.pid for p in procs.values()
               if os.path.basename(p.command.split()[0]) == "lockf" and lock in p.command
               and p.pid not in holders]
    waiters = len(set(blocked) | (fds - set(holders)))
    result = []
    for holder in holders:
        tree = _descendants(holder, children)
        client = next((pid for pid in tree if any(m in procs[pid].command for m in _CLIENT_MARKERS)), None)
        daemon = find_daemon(client) if client else None
        build = tree + ([daemon] + children.get(daemon, []) if daemon else [])
        result.append(Holding(lock, holder, waiters, client, daemon, build))
    return result


def _state_path(payload: dict) -> Path:
    return Path(os.path.expanduser(payload.get("state_dir") or "~/.local/state/psk")) / _STATE_FILE


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def tick(settings: dict, state: dict, procs: Dict[int, Proc], now: float, find_daemon=daemon_of) -> List[dict]:
    idle_seconds = float(settings.get("idle-minutes", 10)) * 60
    max_hold_seconds = float(settings.get("max-hold-minutes", 30)) * 60
    active_cpu = float(settings.get("active-cpu-seconds", 2.0))
    seen, targets = {}, []
    for lock in settings.get("locks", [DEFAULT_LOCK]):
        for h in holdings(lock, procs, find_daemon):
            holder = procs[h.holder]
            key = f"{lock}|{h.holder}|{int((now - holder.etime) // 10)}"
            cpu = sum(procs[pid].cpu for pid in h.build if pid in procs)
            prev = state.get(key)
            active = prev is None or cpu - prev["cpu"] >= active_cpu
            entry = {"cpu": cpu, "last_active": now if active else prev["last_active"],
                     "holder": h.holder, "build": h.build, "lock": lock}
            seen[key] = entry
            idle = now - entry["last_active"]
            orphan = holder.ppid == 1
            if prev is None or h.client is None or not h.waiters or idle < idle_seconds:
                continue
            if not orphan and holder.etime < max_hold_seconds:
                continue
            targets.append({"pid": h.client, "reason": (
                f"{os.path.basename(lock)} held {holder.etime // 60}m, build idle {int(idle // 60)}m, "
                f"waiters {h.waiters}, holder {'orphaned' if orphan else 'parent alive'}")})
    state.clear()
    state.update(seen)
    return targets


def post_kill(settings: dict, state: dict, killed: List[dict], wait_seconds: float,
              take_snapshot=snapshot, sleep=time.sleep) -> List[dict]:
    killed_pids = {int(k["pid"]) for k in killed}
    affected = {e["holder"]: e for e in state.values() if killed_pids & set(e["build"])}
    if not affected:
        return []
    deadline = time.monotonic() + wait_seconds
    while True:
        procs = take_snapshot()
        still = [e for holder, e in affected.items()
                 if _live(holder, procs) and holder in lock_fds(e["lock"])]
        if not still or time.monotonic() >= deadline:
            break
        sleep(1)
    targets = []
    children = _children(procs)
    for e in still:
        reason = f"{os.path.basename(e['lock'])} still held {int(wait_seconds)}s after its build was killed"
        for pid in [*_descendants(e["holder"], children), e["holder"]]:
            if _live(pid, procs):
                targets.append({"pid": pid, "reason": reason})
    return targets


def main() -> int:
    payload = json.load(sys.stdin)
    settings = payload.get("settings", {})
    path = _state_path(payload)
    state = _load(path)
    if payload.get("event") == "post-kill":
        targets = post_kill(settings, state, payload.get("killed", []),
                            float(settings.get("release-wait-seconds", 15)))
    else:
        targets = tick(settings, state, snapshot(), time.time())
        _save(path, state)
    json.dump({"targets": targets}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
