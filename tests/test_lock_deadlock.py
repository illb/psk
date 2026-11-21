import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_killer import hooks as hooks_module
from src.process_killer.hooks import Hook, HookRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
import gradle_lock_stall as stall  # noqa: E402
import lock_deadlock as deadlock  # noqa: E402

G, D = "/tmp/t-gradle.lock", "/tmp/t-docker.lock"


def proc(pid, ppid, command):
    return stall.Proc(pid, ppid, 600, 0.0, "S", command)


def table_1121(extra_gradle_waiters=12):
    rows = [
        proc(50, 1, "claude --resume"),
        proc(15908, 50, f"lockf -k {G} proj local-build"),
        proc(28397, 15908, "python proj local-build"),
        proc(60, 1, "-zsh"),
        proc(14555, 60, f"lockf -k {D} proj local-build"),
        proc(14556, 14555, "python proj local-build"),
        proc(26239, 14556, f"lockf -k {G} ./gradlew bootJar"),
    ]
    rows += [proc(30000 + i, 70, f"lockf -k {G} ./gradlew test") for i in range(extra_gradle_waiters)]
    return {p.pid: p for p in rows}


FDS_1121 = {G: {15908, 28397}, D: {28397, 14555, 14556}}


def detect(procs, fds=FDS_1121):
    return deadlock.detect([G, D], procs, fds_of=lambda lock: fds[lock], start_of=lambda pid: "t")


class DetectTests(unittest.TestCase):
    def test_1121_shape_is_one_cycle_and_the_victim_frees_the_busier_lock(self):
        cycles = detect(table_1121())
        self.assertEqual(len(cycles), 1)
        cycle = cycles[0]
        self.assertEqual(cycle.holders, {G: 15908, D: 14555})
        self.assertEqual(cycle.waiters, {G: 13, D: 1})
        self.assertEqual(cycle.victim, 28397)

    def test_fd_opened_under_an_outer_holder_is_neither_holder_nor_waiter(self):
        view = deadlock.view(D, table_1121(), FDS_1121[D])
        self.assertEqual(view.holders, [14555])
        self.assertEqual(view.waiters, {28397})

    def test_waiting_without_a_cycle_is_not_a_deadlock(self):
        procs = table_1121()
        del procs[26239]
        self.assertEqual(detect(procs), [])

    def test_nested_lockf_on_the_held_lock_is_a_self_cycle(self):
        procs = {p.pid: p for p in [proc(100, 1, f"lockf -k {G} sh -c x"), proc(101, 100, "sh -c x"),
                                     proc(102, 101, f"lockf -k {G} ./gradlew")]}
        cycles = detect(procs, {G: {100}, D: set()})
        self.assertEqual([(c.locks, c.victim) for c in cycles], [([G], 102)])


class TickTests(unittest.TestCase):
    def run_tick(self, state, settings=None, procs=None):
        sent = []
        result = deadlock.tick({"locks": [G, D], **(settings or {})}, state, procs or table_1121(),
                               fds_of=lambda lock: FDS_1121[lock], panes_of=lambda: {50: "main:1.0"},
                               notify=lambda title, msg: sent.append(msg), start_of=lambda pid: "t")
        return result, sent

    def test_confirmed_on_the_second_tick_notified_once_and_not_killed_by_default(self):
        state = {}
        with patch.object(deadlock, "_cwd", return_value="asdp-cm"):
            first, sent1 = self.run_tick(state)
            second, sent2 = self.run_tick(state)
            third, sent3 = self.run_tick(state)
        self.assertEqual((first["notices"], sent1), ([], []))
        notice = second["notices"][0]
        self.assertEqual((notice["locks"], notice["holders"], notice["waiters"], notice["victim"]),
                         (["t-docker.lock", "t-gradle.lock"], [14555, 15908], [1, 13], 28397))
        self.assertIn("resolve " + notice["cycle"], notice["resolve"])
        self.assertIn("agent=claude agent_pid=50 cwd=asdp-cm tmux=main:1.0", notice["detail"][1])
        self.assertIn("풀기:", sent2[0])
        self.assertEqual([second["targets"], third["notices"], third["targets"], sent3], [[], [], [], []])

    def test_kill_action_targets_only_the_victim(self):
        state = {}
        with patch.object(deadlock, "_cwd", return_value=""):
            self.run_tick(state, {"deadlock-action": "kill"})
            result, _ = self.run_tick(state, {"deadlock-action": "kill"})
        self.assertEqual([t["pid"] for t in result["targets"]], [28397])

    def test_a_gone_cycle_is_forgotten(self):
        state = {}
        self.run_tick(state)
        procs = table_1121()
        del procs[26239]
        self.run_tick(state, procs=procs)
        self.assertEqual(state, {})


class NoticeAuditTests(unittest.TestCase):
    def test_hook_notices_are_audited(self):
        events = []
        body = "import json\nprint(json.dumps({'targets': [], 'notices': [{'kind': 'k', 'detail': ['a'] * 50}]}))"
        runner = HookRunner([Hook("n", [sys.executable, "-c", body])], audit=events.append)
        runner.tick()
        notice = next(e for e in events if e["event"] == "hook-notice")
        self.assertEqual((notice["hook"], notice["kind"], len(notice["detail"])), ("n", "k", hooks_module._NOTICE_FIELDS))


def wait_until(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


class RealDeadlockTests(unittest.TestCase):
    """Two real lockf holders whose children wait for each other's lock; resolve frees both."""

    def test_detect_then_resolve_releases_both_locks(self):
        tmp = Path(tempfile.mkdtemp())
        a, b = str(tmp / "a.lock"), str(tmp / "b.lock")
        done_a, done_b = tmp / "done-a", tmp / "done-b"
        first = subprocess.Popen(["lockf", "-k", a, "sh", "-c", f"sleep 1 && lockf -k {b} true && touch {done_a}"],
                                 start_new_session=True)
        second = subprocess.Popen(["lockf", "-k", b, "sh", "-c", f"sleep 1 && lockf -k {a} true && touch {done_b}"],
                                  start_new_session=True)
        extra = subprocess.Popen(["lockf", "-k", a, "true"], start_new_session=True)
        procs = [first, second, extra]
        try:
            self.assertTrue(wait_until(lambda: len(deadlock.detect([a, b], stall.snapshot())) == 1))
            settings = {"locks": [a, b], "notify-macos": False}
            command = [sys.executable, str(ROOT / "hooks" / "lock_deadlock.py")]
            payload = json.dumps({"event": "tick", "settings": settings, "state_dir": str(tmp)})
            run = lambda: json.loads(subprocess.run(command, input=payload, capture_output=True,  # noqa: E731
                                                    text=True, check=True).stdout)
            self.assertEqual(run()["notices"], [])
            notice = run()["notices"][0]
            self.assertEqual(notice["waiters"][0], 2)
            self.assertFalse(done_a.exists() or done_b.exists())
            log = tmp / "psk.log"
            out = subprocess.run([*command, "resolve", notice["cycle"], "--locks", a, b, "--log", str(log)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertEqual(json.loads(out.stdout)["killed"], [notice["victim"]])
            self.assertTrue(wait_until(done_b.exists))
            for p in procs:
                p.wait(timeout=10)
            self.assertFalse(done_a.exists())
            self.assertTrue(Path(a).exists() and Path(b).exists())
            self.assertIn('"hook-target"', log.read_text())
            again = subprocess.run([*command, "resolve", notice["cycle"], "--locks", a, b, "--log", str(log)],
                                   capture_output=True, text=True)
            self.assertEqual(again.returncode, 1)
        finally:
            for p in procs:
                if p.poll() is None:
                    try:
                        import os
                        os.killpg(p.pid, 9)
                    except OSError:
                        pass
                    p.wait()


if __name__ == "__main__":
    unittest.main()
