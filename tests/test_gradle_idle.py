import json
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_killer.categories import CATEGORY_BY_KEY
from src.process_killer.category_killer import CategoryKiller
from src.process_killer.collector import ProcessCollector
from src.process_killer.daemon import DEFAULT_CATEGORIES
from src.process_killer.idle_tracker import IdleTracker
from src.process_killer.models import ProcessInfo

GRADLE = "/opt/jdk/bin/java -Xmx2g org.gradle.launcher.daemon.bootstrap.GradleDaemon 8.14"
KOTLIN = "/opt/jdk/bin/java org.jetbrains.kotlin.daemon.KotlinCompileDaemon --daemon-runFilesPath x"


def process(pid=910001, *, ppid="1", command=GRADLE, cpu=0.0, cpu_time=100.0, etime=7200):
    return ProcessInfo(user="tester", pid=pid, ppid=ppid, cpu=cpu, mem=0, stat="S",
                       start="00:00", uptime="2h", command=command, name="java",
                       type="java", etime_seconds=etime, cpu_time_seconds=cpu_time)


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


class CpuTimeParseTests(unittest.TestCase):
    def test_parse_cpu_time_formats(self):
        parse = ProcessCollector._parse_cpu_time
        self.assertAlmostEqual(parse("28:26.17"), 1706.17)
        self.assertAlmostEqual(parse("1:02:03.5"), 3723.5)
        self.assertEqual(parse("2-01:00:00"), 2 * 86400 + 3600)
        self.assertEqual(parse("garbage"), 0.0)


class IdleTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.tracker = IdleTracker(str(Path(self.tmp.name) / "idle.json"), clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def observe(self, *, advance, cpu_time, etime=None, cpu=0.0, pid=910001, command=GRADLE):
        self.clock.now += advance
        self._etime = (etime if etime is not None
                       else getattr(self, "_etime", 7200) + int(advance))
        proc = process(pid, cpu=cpu, cpu_time=cpu_time, etime=self._etime, command=command)
        self.tracker.annotate([proc])
        return proc

    def test_housekeeping_cpu_accumulates_idle_until_threshold(self):
        first = self.observe(advance=0, cpu_time=100.0)
        self.assertIsNone(first.idle_seconds)
        self.assertFalse(CATEGORY_BY_KEY["gradle-idle"].matcher(first))

        half = self.observe(advance=1800, cpu_time=101.8)
        self.assertEqual(half.idle_seconds, 1800)
        self.assertFalse(CATEGORY_BY_KEY["gradle-idle"].matcher(half))

    def test_kotlin_daemon_is_tracked(self):
        self.observe(advance=0, cpu_time=10.0, command=KOTLIN)
        later = self.observe(advance=3600, cpu_time=11.0, command=KOTLIN)
        self.assertEqual(later.idle_seconds, 3600)
        self.assertTrue(CATEGORY_BY_KEY["gradle-idle"].matcher(later))

    def test_long_idle_daemon_matches_after_an_hour(self):
        self.observe(advance=0, cpu_time=100.0)
        self.observe(advance=1800, cpu_time=101.8)
        hour = self.observe(advance=1800, cpu_time=103.6)
        self.assertEqual(hour.idle_seconds, 3600)
        self.assertTrue(CATEGORY_BY_KEY["gradle-idle"].matcher(hour))
        self.assertEqual(CATEGORY_BY_KEY["gradle-idle"].reason(hour), "no build CPU for 60m")

    def test_build_activity_resets_idle(self):
        self.observe(advance=0, cpu_time=100.0)
        self.observe(advance=1800, cpu_time=101.0)
        built = self.observe(advance=1800, cpu_time=160.0)
        self.assertEqual(built.idle_seconds, 0)
        later = self.observe(advance=1800, cpu_time=161.0)
        self.assertEqual(later.idle_seconds, 1800)

    def test_current_cpu_counts_as_activity(self):
        self.observe(advance=0, cpu_time=100.0)
        busy = self.observe(advance=3600, cpu_time=100.5, cpu=35.0)
        self.assertEqual(busy.idle_seconds, 0)

    def test_pid_reuse_starts_over_and_dead_pids_are_pruned(self):
        self.observe(advance=0, cpu_time=100.0)
        reused = self.observe(advance=3600, cpu_time=1.0, etime=60)
        self.assertIsNone(reused.idle_seconds)

        self.clock.now += 60
        self.tracker.annotate([process(910002, cpu_time=5.0, etime=120)])
        state = json.loads(self.tracker.path.read_text())
        self.assertEqual(set(state), {"910002"})

    def test_non_gradle_processes_are_ignored(self):
        proc = process(command="/usr/bin/python3 worker.py")
        self.tracker.annotate([proc])
        self.assertIsNone(proc.idle_seconds)
        self.assertEqual(json.loads(self.tracker.path.read_text()), {})


class GradleIdleKillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.tracker = IdleTracker(str(Path(self.tmp.name) / "idle.json"), clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cycle(self, processes, advance):
        self.clock.now += advance
        for proc in processes:
            proc.etime_seconds += int(advance)
        killer = CategoryKiller(idle_tracker=self.tracker)
        with patch.object(killer.collector, "get_process_info", return_value=processes), \
                patch.object(killer, "_self_and_ancestors", return_value=set()), \
                patch.object(killer, "_alive", return_value=False), \
                patch("src.process_killer.category_killer.time.sleep"), \
                patch("src.process_killer.category_killer.os.kill") as send:
            result = killer.kill_categories(["gradle-idle"], quiet=True)
        return result, send

    def test_idle_daemon_is_terminated_but_active_build_tree_is_protected(self):
        wrapper = process(910010, command="java org.gradle.wrapper.GradleWrapperMain build",
                          cpu_time=5.0)
        building = process(910011, ppid=str(wrapper.pid), cpu_time=50.0)
        idle = process(910012, cpu_time=80.0)
        procs = [wrapper, building, idle]

        result, send = self.run_cycle(procs, 0)
        self.assertEqual(result["targeted"], 0)
        result, send = self.run_cycle(procs, 1800)
        self.assertEqual(result["targeted"], 0)
        result, send = self.run_cycle(procs, 1800)

        self.assertEqual(result["targeted"], 1)
        self.assertEqual(result["by_category"], {"gradle-idle": 1})
        send.assert_called_once_with(idle.pid, signal.SIGTERM)

    def test_daemon_schedules_gradle_idle_but_not_snapshot_gradle(self):
        self.assertIn("gradle-idle", DEFAULT_CATEGORIES)
        self.assertNotIn("gradle", DEFAULT_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
