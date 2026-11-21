"""psk hook: shared build locks waiting on each other (a holder's tree waits for a lock another holder's
tree holds, back around to the first lock).

tick: a cycle seen on two ticks in a row is confirmed → audit notice + macOS notification. With
`deadlock-action: kill` the victim is returned as a target; the default `notify` leaves it to
`lock_deadlock.py resolve <id>`, which re-detects and kills only when the same cycle is still there.
Victim: inside the tree holding the lock with the most waiters, the one process waiting for the next
lock. Lock files are never removed.
"""
import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gradle_lock_stall import (  # noqa: E402
    Proc, _children, _descendants, _live, _load, _save, lock_fds, snapshot)

DEFAULT_LOCKS = ["/tmp/as-incubator-gradle.lock", "/tmp/docker-amd64-build.lock"]
HOOK_NAME = "lock-deadlock"
_STATE_FILE = "lock-deadlock.json"
_OWNER_EXECUTABLES = {"claude", "codex"}


def _exe(proc: Proc) -> str:
    tokens = proc.command.split()
    return os.path.basename(tokens[0]) if tokens else ""


def _ancestors(pid: int, procs: Dict[int, Proc]) -> List[int]:
    chain, seen = [], {pid}
    while pid in procs and procs[pid].ppid > 1 and procs[pid].ppid not in seen:
        pid = procs[pid].ppid
        seen.add(pid)
        chain.append(pid)
    return chain


def _lockf_waits_on(proc: Proc, lock: str) -> bool:
    tokens = proc.command.split()
    return bool(tokens) and os.path.basename(tokens[0]) == "lockf" and lock in tokens[1:5]


@dataclass
class LockView:
    lock: str
    holders: List[int]
    waiters: Set[int]


def view(lock: str, procs: Dict[int, Proc], fds: Set[int]) -> LockView:
    children = _children(procs)
    has_child = {pid for pid in fds if any(_live(c, procs) for c in children.get(pid, []))}
    under_fd = {pid for pid in fds if set(_ancestors(pid, procs)) & fds}
    holders = sorted(pid for pid in has_child if pid not in under_fd and _live(pid, procs))
    lockf_waiters = {p.pid for p in procs.values()
                     if p.pid not in fds and _live(p.pid, procs) and _lockf_waits_on(p, lock)}
    fd_waiters = {pid for pid in fds - has_child - under_fd if _live(pid, procs)}
    return LockView(lock, holders, lockf_waiters | fd_waiters)


@dataclass
class Cycle:
    id: str
    locks: List[str]
    holders: Dict[str, int]
    waiters: Dict[str, int]
    edges: List[dict] = field(default_factory=list)
    victim: Optional[int] = None


def _edges(views: Dict[str, LockView], procs: Dict[int, Proc]) -> Dict[str, List[dict]]:
    children = _children(procs)
    out: Dict[str, List[dict]] = {}
    for src, v in views.items():
        for holder in v.holders:
            tree = set(_descendants(holder, children))
            for dst, w in views.items():
                for waiter in sorted(w.waiters & tree):
                    out.setdefault(src, []).append({"from": src, "holder": holder, "waiter": waiter, "to": dst})
    return out


def _cycles_from(start: str, edges: Dict[str, List[dict]]) -> List[List[dict]]:
    found, stack = [], [(start, [])]
    while stack:
        lock, path = stack.pop()
        for edge in edges.get(lock, []):
            if edge["to"] == start:
                found.append(path + [edge])
            elif edge["to"] > start and all(e["from"] != edge["to"] for e in path):
                stack.append((edge["to"], path + [edge]))
    return found


def started(pid: int) -> str:
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                          timeout=10).stdout.strip()


def detect(locks: List[str], procs: Dict[int, Proc], fds_of=lock_fds, start_of=started) -> List[Cycle]:
    views = {lock: view(lock, procs, fds_of(lock)) for lock in locks}
    edges = _edges(views, procs)
    cycles, seen = [], set()
    for start in sorted(edges):
        for path in _cycles_from(start, edges):
            holders = {e["from"]: e["holder"] for e in path}
            key = "|".join(sorted(f"{lock}:{pid}:{start_of(pid)}" for lock, pid in holders.items()))
            if key in seen:
                continue
            seen.add(key)
            waiters = {e["from"]: len(views[e["from"]].waiters) for e in path}
            release = max(path, key=lambda e: (waiters[e["from"]], -path.index(e)))
            cycles.append(Cycle(hashlib.sha1(key.encode()).hexdigest()[:10], [e["from"] for e in path],
                                holders, waiters, path, release["waiter"]))
    return cycles


def _cwd(pid: int) -> str:
    out = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True,
                         text=True, timeout=10).stdout
    return next((os.path.basename(line[1:]) for line in out.splitlines() if line.startswith("n")), "")


def _panes() -> Dict[int, str]:
    try:
        out = subprocess.run(["tmux", "list-panes", "-a", "-F",
                              "#{pane_pid} #{session_name}:#{window_index}.#{pane_index}"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return {int(pid): name for pid, _, name in (line.partition(" ") for line in out.splitlines())
            if pid.isdigit()}


def owner(pid: int, procs: Dict[int, Proc], panes: Dict[int, str]) -> dict:
    chain = [pid, *_ancestors(pid, procs)]
    info: dict = {}
    agent = next((p for p in chain if p in procs and _exe(procs[p]) in _OWNER_EXECUTABLES), None)
    if agent:
        info.update(agent=_exe(procs[agent]), agent_pid=agent, cwd=_cwd(agent))
    pane = next((panes[p] for p in chain if p in panes), None)
    if pane:
        info["tmux"] = pane
    return info


def _describe(cycle: Cycle, procs: Dict[int, Proc], panes: Dict[int, str]) -> List[str]:
    parts = []
    for edge in cycle.edges:
        who = owner(edge["holder"], procs, panes)
        where = " ".join(f"{k}={v}" for k, v in who.items()) or "owner unknown"
        parts.append(f"{os.path.basename(edge['from'])} holder {edge['holder']} ({where}), "
                     f"waiters {cycle.waiters[edge['from']]}, its {edge['waiter']} waits "
                     f"{os.path.basename(edge['to'])}")
    return parts


def resolve_command(cycle_id: str) -> str:
    return f"{sys.executable} -I {Path(__file__).resolve()} resolve {cycle_id}"


def _notify_macos(title: str, message: str) -> None:
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def tick(settings: dict, state: dict, procs: Dict[int, Proc], fds_of=lock_fds, panes_of=_panes,
         notify=_notify_macos, start_of=started) -> dict:
    action = settings.get("deadlock-action", "notify")
    current, targets, notices = {}, [], []
    for cycle in detect(settings.get("locks", DEFAULT_LOCKS), procs, fds_of, start_of):
        prev = state.get(cycle.id)
        entry = {"seen": (prev or {}).get("seen", 0) + 1, "notified": (prev or {}).get("notified", False),
                 "victim": cycle.victim}
        current[cycle.id] = entry
        if prev is None:
            continue
        reason = f"lock deadlock {cycle.id}: " + " / ".join(
            f"{os.path.basename(e['from'])}->{os.path.basename(e['to'])}" for e in cycle.edges)
        if not entry["notified"]:
            entry["notified"] = True
            detail = _describe(cycle, procs, panes_of())
            command = resolve_command(cycle.id)
            notices.append({"kind": "lock-deadlock", "cycle": cycle.id, "action": action,
                            "locks": [os.path.basename(lock) for lock in cycle.locks],
                            "holders": [cycle.holders[lock] for lock in cycle.locks],
                            "waiters": [cycle.waiters[lock] for lock in cycle.locks],
                            "victim": cycle.victim, "detail": detail,
                            "resolve": command if action != "kill" else ""})
            if settings.get("notify-macos", True):
                notify("psk: 빌드 잠금 교착", "; ".join(detail)
                       + ("" if action == "kill" else f" — 풀기: {command}"))
        if action == "kill" and cycle.victim:
            targets.append({"pid": cycle.victim, "reason": reason})
    state.clear()
    state.update(current)
    return {"targets": targets, "notices": notices}


def _state_path(state_dir: Optional[str]) -> Path:
    return Path(os.path.expanduser(state_dir or "~/.local/state/psk")) / _STATE_FILE


def _configured_settings(hooks_path: str) -> dict:
    try:
        data = json.loads(Path(hooks_path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for item in data.get("hooks", []):
        if item.get("name") == HOOK_NAME or any("lock_deadlock" in str(c) for c in item.get("command", [])):
            return dict(item.get("settings", {}))
    return {}


def resolve(cycle_id: str, locks: List[str], log_path: Optional[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from src.process_killer.daemon import _auditor  # noqa: E402
    from src.process_killer.hooks import Hook, HookRunner  # noqa: E402

    cycle = next((c for c in detect(locks, snapshot()) if c.id == cycle_id), None)
    if cycle is None or not cycle.victim:
        print(f"cycle {cycle_id} is not present now — nothing killed")
        return 1
    audit = _auditor(Path(log_path).expanduser() if log_path else None, f"{os.getpid()}-resolve")
    runner = HookRunner([], audit=audit)
    reason = f"lock deadlock {cycle_id} resolved by user"
    with contextlib.redirect_stdout(sys.stderr):
        killed = runner._kill(Hook(HOOK_NAME, []), [{"pid": cycle.victim, "reason": reason}])
    print(json.dumps({"cycle": cycle_id, "victim": cycle.victim, "killed": [k["pid"] for k in killed]}))
    return 0 if killed else 2


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "resolve":
        parser = argparse.ArgumentParser(prog="lock_deadlock.py resolve")
        parser.add_argument("cycle_id")
        parser.add_argument("--locks", nargs="+")
        parser.add_argument("--hooks", default="~/.config/psk/hooks.json")
        parser.add_argument("--log", default="~/Library/Logs/psk-daemon.log")
        args = parser.parse_args(argv[1:])
        locks = args.locks or _configured_settings(args.hooks).get("locks", DEFAULT_LOCKS)
        return resolve(args.cycle_id, locks, args.log or None)
    payload = json.load(sys.stdin)
    if payload.get("event") != "tick":
        json.dump({"targets": []}, sys.stdout)
        return 0
    path = _state_path(payload.get("state_dir"))
    state = _load(path)
    result = tick(payload.get("settings", {}), state, snapshot())
    _save(path, state)
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
