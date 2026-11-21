"""Personal policy hooks: external commands that pick extra kill targets on a schedule and after kills."""
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

DEFAULT_HOOKS_PATH = "~/.config/psk/hooks.json"
DEFAULT_STATE_DIR = "~/.local/state/psk"
TERM_GRACE_SECONDS = 5.0
_PROTECTED_EXECUTABLES = {"claude", "codex", "launchd", "tmux", "sshd", "login"}
_REASON_LIMIT = 300
_NOTICE_FIELDS = 20


@dataclass(frozen=True)
class Hook:
    name: str
    command: List[str]
    interval_seconds: int = 120
    timeout_seconds: int = 60
    settings: dict = field(default_factory=dict)


def load_hooks(path: Optional[str]) -> List[Hook]:
    if not path:
        return []
    file = Path(path).expanduser()
    if not file.is_file():
        return []
    data = json.loads(file.read_text(encoding="utf-8"))
    hooks = []
    for item in data.get("hooks", []):
        if item.get("enabled", True) is False:
            continue
        command = [os.path.expanduser(str(part)) for part in item["command"]]
        if not command:
            raise ValueError(f"hook {item.get('name')!r} has an empty command")
        hooks.append(Hook(
            name=str(item["name"]),
            command=command,
            interval_seconds=max(10, int(item.get("interval-seconds", 120))),
            timeout_seconds=max(5, int(item.get("timeout-seconds", 60))),
            settings=dict(item.get("settings", {})),
        ))
    return hooks


def _scalar(value):
    if isinstance(value, str):
        return value[:_REASON_LIMIT]
    return value if isinstance(value, (int, float, bool)) or value is None else str(value)[:_REASON_LIMIT]


def _clean_notice(notice: dict) -> dict:
    clean = {}
    for key, value in list(notice.items())[:_NOTICE_FIELDS]:
        if isinstance(value, list):
            clean[str(key)] = [_scalar(v) for v in value[:_NOTICE_FIELDS]]
        else:
            clean[str(key)] = _scalar(value)
    return clean


def _ps_table() -> Dict[int, tuple]:
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,uid=,command="], capture_output=True,
                         text=True, timeout=10).stdout
    table = {}
    for line in out.splitlines():
        fields = line.split(None, 3)
        if len(fields) >= 3 and fields[0].isdigit():
            table[int(fields[0])] = (int(fields[1]), int(fields[2]), fields[3] if len(fields) > 3 else "")
    return table


def _executable(command: str) -> str:
    tokens = command.split()
    return os.path.basename(tokens[0])[:80] if tokens else "unknown"


def _self_and_ancestors(table: Dict[int, tuple]) -> Set[int]:
    excluded, pid = set(), os.getpid()
    while pid > 0 and pid not in excluded:
        excluded.add(pid)
        pid = table.get(pid, (0,))[0]
    return excluded


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class HookRunner:
    def __init__(self, hooks: List[Hook], audit: Callable[[dict], None],
                 state_dir: str = DEFAULT_STATE_DIR, clock: Callable[[], float] = time.monotonic,
                 grace_seconds: float = TERM_GRACE_SECONDS):
        self.hooks = hooks
        self.audit = audit
        self.state_dir = str(Path(state_dir).expanduser())
        self.clock = clock
        self.grace_seconds = grace_seconds
        self._next_run = {hook.name: 0.0 for hook in hooks}

    def tick(self) -> List[dict]:
        """Run hooks whose interval elapsed; kills from them get one post-kill round."""
        now = self.clock()
        killed = []
        for hook in self.hooks:
            if now < self._next_run[hook.name]:
                continue
            self._next_run[hook.name] = now + hook.interval_seconds
            killed += self._kill(hook, self._call(hook, "tick", []))
        if killed:
            killed += self.post_kill(killed)
        return killed

    def post_kill(self, killed: List[dict]) -> List[dict]:
        extra = []
        for hook in self.hooks:
            extra += self._kill(hook, self._call(hook, "post-kill", killed))
        return extra

    def _call(self, hook: Hook, event: str, killed: List[dict]) -> List[dict]:
        payload = {"event": event, "hook": hook.name, "settings": hook.settings,
                   "killed": killed, "state_dir": self.state_dir}
        try:
            result = subprocess.run(hook.command, input=json.dumps(payload), capture_output=True,
                                    text=True, timeout=hook.timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as error:
            self.audit({"event": "hook-error", "hook": hook.name, "hook_event": event,
                        "error": type(error).__name__})
            return []
        if result.returncode != 0:
            self.audit({"event": "hook-error", "hook": hook.name, "hook_event": event,
                        "error": "exit", "exit_code": result.returncode})
            return []
        try:
            data = json.loads(result.stdout or "{}")
            targets = data.get("targets", [])
            notices = data.get("notices", [])
        except (ValueError, AttributeError):
            self.audit({"event": "hook-error", "hook": hook.name, "hook_event": event, "error": "output"})
            return []
        for notice in notices if isinstance(notices, list) else []:
            if isinstance(notice, dict):
                self.audit({**_clean_notice(notice), "event": "hook-notice", "hook": hook.name,
                            "hook_event": event})
        return targets if isinstance(targets, list) else []

    def _kill(self, hook: Hook, targets: List[dict]) -> List[dict]:
        if not targets:
            return []
        try:
            table = _ps_table()
        except (OSError, subprocess.SubprocessError):
            self.audit({"event": "hook-error", "hook": hook.name, "error": "ps"})
            return []
        excluded = _self_and_ancestors(table)
        chosen: Dict[int, str] = {}
        for target in targets:
            try:
                pid = int(target["pid"])
            except (KeyError, TypeError, ValueError):
                continue
            reason = str(target.get("reason", ""))[:_REASON_LIMIT]
            entry = table.get(pid)
            skip = None
            if entry is None:
                skip = "gone"
            elif pid <= 1 or pid in excluded:
                skip = "self-or-ancestor"
            elif entry[1] != os.getuid():
                skip = "other-user"
            elif _executable(entry[2]) in _PROTECTED_EXECUTABLES:
                skip = "protected-executable"
            self.audit({"event": "hook-target", "hook": hook.name, "process_pid": pid,
                        "executable": _executable(entry[2]) if entry else "unknown",
                        "reason": reason, "selected": skip is None, **({"skip": skip} if skip else {})})
            if skip is None:
                chosen[pid] = reason
        return self._terminate(hook, chosen)

    def _signal(self, hook: Hook, pid: int, sig: signal.Signals) -> bool:
        try:
            os.kill(pid, sig)
        except OSError as error:
            self.audit({"event": "signal", "hook": hook.name, "target_pid": pid, "signal": sig.name,
                        "outcome": "error", "errno": error.errno})
            return False
        self.audit({"event": "signal", "hook": hook.name, "target_pid": pid, "signal": sig.name,
                    "outcome": "sent"})
        return True

    def _terminate(self, hook: Hook, chosen: Dict[int, str]) -> List[dict]:
        sent = [pid for pid in chosen if self._signal(hook, pid, signal.SIGTERM)]
        if not sent:
            return []
        deadline = time.monotonic() + self.grace_seconds
        while time.monotonic() < deadline and any(_alive(pid) for pid in sent):
            time.sleep(0.2)
        for pid in [pid for pid in sent if _alive(pid)]:
            self._signal(hook, pid, signal.SIGKILL)
        time.sleep(0.5)
        killed = []
        for pid in sent:
            alive = _alive(pid)
            self.audit({"event": "observed", "hook": hook.name, "target_pid": pid, "alive": alive})
            if not alive:
                killed.append({"pid": pid, "category": f"hook:{hook.name}", "reason": chosen[pid]})
        return killed
