import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_killer import hooks as hooks_module
from src.process_killer.daemon import _run_cycle
from src.process_killer.hooks import Hook, HookRunner, load_hooks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
import gradle_lock_stall as stall  # noqa: E402

FAKE_CLIENT = "java org.gradle.wrapper.GradleWrapperMain"


def hook_script(body: str) -> list:
    return [sys.executable, "-c", "import json,sys\npayload=json.load(sys.stdin)\n" + body]


def wait_until(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


class LoadHooksTests(unittest.TestCase):
    def test_missing_file_means_no_hooks(self):
        self.assertEqual(load_hooks("/nonexistent/hooks.json"), [])
        self.assertEqual(load_hooks(None), [])

    def test_enabled_hooks_are_loaded_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hooks.json"
            path.write_text(json.dumps({"hooks": [
                {"name": "a", "command": ["~/bin/a"], "settings": {"x": 1}},
                {"name": "b", "command": ["b"], "enabled": False},
            ]}))
            loaded = load_hooks(str(path))
        self.assertEqual([h.name for h in loaded], ["a"])
        self.assertEqual(loaded[0].command, [os.path.expanduser("~/bin/a")])
        self.assertEqual((loaded[0].interval_seconds, loaded[0].settings), (120, {"x": 1}))


class HookRunnerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        out = subprocess.run(["sh", "-c", "sleep 60 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True)
        self.victim = Orphan(int(out.stdout))

    def tearDown(self):
        self.victim.kill()

    def runner(self, body: str, clock=lambda: 0.0, interval=120):
        hook = Hook("t", hook_script(body), interval_seconds=interval)
        return HookRunner([hook], audit=self.events.append, clock=clock, grace_seconds=1.0)

    def test_tick_kills_the_target_and_audits_without_command_arguments(self):
        body = (f"print(json.dumps({{'targets': [{{'pid': {self.victim.pid}, 'reason': 'stalled'}}]}}"
                ") if payload['event'] == 'tick' else '{}')")
        killed = self.runner(body).tick()
        self.assertEqual(killed, [{"pid": self.victim.pid, "category": "hook:t", "reason": "stalled"}])
        self.assertIsNotNone(self.victim.poll())
        target = next(e for e in self.events if e["event"] == "hook-target")
        self.assertEqual((target["executable"], target["selected"]), ("sleep", True))
        self.assertNotIn("60", json.dumps(self.events))

    def test_self_and_gone_targets_are_skipped(self):
        body = f"print(json.dumps({{'targets': [{{'pid': {os.getpid()}}}, {{'pid': 999999}}]}}))"
        self.assertEqual(self.runner(body).tick(), [])
        skips = sorted(e.get("skip") for e in self.events if e["event"] == "hook-target")
        self.assertEqual(skips, ["gone", "self-or-ancestor"])
        self.assertIsNone(self.victim.poll())

    def test_hook_runs_on_its_own_interval(self):
        now = [0.0]
        runner = self.runner("print('{}')", clock=lambda: now[0], interval=60)
        with patch.object(runner, "_call", wraps=runner._call) as call:
            runner.tick()
            now[0] = 30.0
            runner.tick()
            now[0] = 61.0
            runner.tick()
        self.assertEqual(call.call_count, 2)

    def test_kills_from_a_tick_get_a_post_kill_round(self):
        marker = Path(tempfile.mkdtemp()) / "killed.json"
        body = (f"import pathlib\n"
                f"if payload['event'] == 'tick':\n"
                f"    print(json.dumps({{'targets': [{{'pid': {self.victim.pid}}}]}}))\n"
                f"else:\n"
                f"    pathlib.Path({str(marker)!r}).write_text(json.dumps(payload['killed']))\n"
                f"    print('{{}}')\n")
        self.runner(body).tick()
        self.assertEqual(json.loads(marker.read_text())[0]["pid"], self.victim.pid)

    def test_failing_hook_is_audited_and_ignored(self):
        self.assertEqual(self.runner("sys.exit(3)").tick(), [])
        self.assertEqual(self.events[-1]["exit_code"], 3)

    def test_daemon_cycle_hands_category_kills_to_post_kill(self):
        runner = self.runner("print('{}')")
        summary = {"targeted": 1, "killed": 1, "killed_pids": [{"pid": 4242, "category": "gradle-stuck"}],
                   "reap_signals": 0, "by_category": {}}
        with patch("src.process_killer.daemon.CategoryKiller") as killer, \
                patch.object(runner, "post_kill", return_value=[]) as post:
            killer.return_value.kill_categories.return_value = summary
            _run_cycle(["gradle-stuck"], None, check_stale_ai=False, hook_runner=runner)
        post.assert_called_once_with(summary["killed_pids"])


class Orphan:
    """A process reparented to launchd, like real hook targets (not this test's child)."""

    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None if hooks_module._alive(self.pid) else 0

    def kill(self):
        try:
            os.kill(self.pid, 9)
        except OSError:
            pass


def proc(pid, ppid, command, etime=3600, cpu=0.0, stat="S"):
    return stall.Proc(pid, ppid, etime, cpu, stat, command)


class GradleLockStallTests(unittest.TestCase):
    LOCK = "/tmp/test-gradle.lock"
    SETTINGS = {"locks": [LOCK], "idle-minutes": 10, "max-hold-minutes": 30, "active-cpu-seconds": 2}

    def procs(self, now, *, holder_ppid=1, holder_age=3600, worker_cpu=5.0, waiter=True):
        table = [
            proc(100, holder_ppid, f"lockf -k {self.LOCK} ./gradlew test", etime=int(holder_age + now)),
            proc(101, 100, FAKE_CLIENT),
            proc(200, 1, "java org.gradle.launcher.daemon.bootstrap.GradleDaemon 9.5.0"),
            proc(201, 200, "java worker.org.gradle.process.internal.worker.GradleWorkerMain", cpu=worker_cpu),
        ]
        if waiter:
            table.append(proc(300, 50, f"lockf -k {self.LOCK} ./gradlew bootJar"))
        return {p.pid: p for p in table}

    def tick(self, state, now, **kwargs):
        with patch.object(stall, "lock_fds", return_value={100}):
            return stall.tick(self.SETTINGS, state, self.procs(now, **kwargs), now, find_daemon=lambda c: 200)

    def test_idle_build_with_waiters_and_orphaned_holder_targets_the_client(self):
        state = {}
        self.assertEqual(self.tick(state, 0.0), [])
        self.assertEqual(self.tick(state, 300.0), [])
        targets = self.tick(state, 660.0)
        self.assertEqual([t["pid"] for t in targets], [101])
        self.assertIn("waiters 1", targets[0]["reason"])
        self.assertIn("orphaned", targets[0]["reason"])

    def test_progressing_build_is_kept(self):
        state = {}
        self.tick(state, 0.0, worker_cpu=5.0)
        self.tick(state, 300.0, worker_cpu=50.0)
        self.assertEqual(self.tick(state, 660.0, worker_cpu=95.0), [])

    def test_no_waiters_keeps_the_build(self):
        state = {}
        self.tick(state, 0.0, waiter=False)
        self.assertEqual(self.tick(state, 900.0, waiter=False), [])

    def test_young_holder_with_a_live_parent_is_kept_until_max_hold(self):
        state = {}
        self.tick(state, 0.0, holder_ppid=77, holder_age=900)
        self.assertEqual(self.tick(state, 660.0, holder_ppid=77, holder_age=900), [])
        self.assertEqual([t["pid"] for t in self.tick(state, 1300.0, holder_ppid=77, holder_age=900)], [101])

    def test_post_kill_takes_the_holder_still_holding_after_its_daemon_died(self):
        state = {"k": {"holder": 100, "build": [101, 200, 201], "lock": self.LOCK, "cpu": 0, "last_active": 0}}
        remaining = {p.pid: p for p in [proc(100, 1, f"lockf -k {self.LOCK} x"), proc(101, 100, FAKE_CLIENT)]}
        with patch.object(stall, "lock_fds", return_value={100}):
            targets = stall.post_kill(self.SETTINGS, state, [{"pid": 200}], 0,
                                      take_snapshot=lambda: remaining, sleep=lambda s: None)
        self.assertEqual(sorted(t["pid"] for t in targets), [100, 101])

    def test_post_kill_ignores_unrelated_or_released_holders(self):
        state = {"k": {"holder": 100, "build": [101], "lock": self.LOCK, "cpu": 0, "last_active": 0}}
        with patch.object(stall, "lock_fds", return_value=set()):
            self.assertEqual(stall.post_kill(self.SETTINGS, state, [{"pid": 101}], 0,
                                             take_snapshot=lambda: {}, sleep=lambda s: None), [])
            self.assertEqual(stall.post_kill(self.SETTINGS, state, [{"pid": 999}], 0), [])


class RealLockTests(unittest.TestCase):
    """A real lockf holder whose 'build' is idle, a real waiter, and the hook freeing the lock."""

    def test_killing_the_stalled_client_frees_the_lock_for_the_waiter(self):
        tmp = Path(tempfile.mkdtemp())
        lock, marker = tmp / "gradle.lock", tmp / "acquired"
        holder = subprocess.Popen(["lockf", "-k", str(lock), "bash", "-c",
                                   f'exec -a "{FAKE_CLIENT}" sleep 300'], start_new_session=True)
        try:
            self.assertTrue(wait_until(lambda: holder.pid in stall.lock_fds(str(lock))))
            waiter = subprocess.Popen(["lockf", "-k", str(lock), "touch", str(marker)])
            settings = {"locks": [str(lock)], "idle-minutes": 0, "max-hold-minutes": 0,
                        "active-cpu-seconds": 1000}
            payload = {"event": "tick", "settings": settings, "state_dir": str(tmp)}
            command = [sys.executable, str(ROOT / "hooks" / "gradle_lock_stall.py")]
            first = subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True)
            self.assertEqual(json.loads(first.stdout), {"targets": []})
            runner = HookRunner([Hook("gradle-lock-stall", command, settings=settings)],
                                audit=lambda e: None, state_dir=str(tmp), grace_seconds=2.0)
            killed = runner.tick()
            self.assertEqual(len(killed), 1)
            self.assertTrue(wait_until(marker.exists))
            self.assertTrue(lock.exists())
            waiter.wait(timeout=10)
        finally:
            if holder.poll() is None:
                os.killpg(holder.pid, 9)
            holder.wait()


if __name__ == "__main__":
    unittest.main()
