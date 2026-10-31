import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_killer.categories import CATEGORY_BY_KEY
from src.process_killer.category_killer import CategoryKiller
from src.process_killer.daemon import DEFAULT_CATEGORIES
from src.process_killer.idle_tracker import IdleTracker
from src.process_killer.models import ProcessInfo

GRADLE = "/opt/jdk/bin/java -Xmx2g org.gradle.launcher.daemon.bootstrap.GradleDaemon 8.14"
KOTLIN = "/opt/jdk/bin/java org.jetbrains.kotlin.daemon.KotlinCompileDaemon --daemon-runFilesPath x"


def process(pid=940001, *, command=KOTLIN, cpu=0.0, cpu_time=100.0, etime=7200):
    return ProcessInfo(user="tester", pid=pid, ppid="1", cpu=cpu, mem=0, stat="S",
                       start="00:00", uptime="2h", command=command, name="java",
                       type="java", etime_seconds=etime, cpu_time_seconds=cpu_time)


class KotlinIdleTrackingTests(unittest.TestCase):
    category = CATEGORY_BY_KEY["kotlin-idle"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1_000_000.0
        self.tracker = IdleTracker(str(Path(self.tmp.name) / "idle.json"), clock=lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def observe(self, proc, *, advance, cpu_time, cpu=0.0):
        self.now += advance
        proc.etime_seconds += int(advance)
        proc.cpu_time_seconds = cpu_time
        proc.cpu = cpu
        self.tracker.annotate([proc])
        return proc

    def test_housekeeping_cpu_still_counts_as_idle(self):
        daemon = process()
        self.observe(daemon, advance=0, cpu_time=100.0)
        self.assertFalse(self.category.matcher(daemon))
        self.observe(daemon, advance=1800, cpu_time=107.0)
        self.assertEqual(daemon.idle_seconds, 1800)
        self.assertTrue(self.category.matcher(daemon))
        self.assertEqual(self.category.reason(daemon), "no compile CPU for 30m")

    def test_compile_cpu_resets_idle(self):
        daemon = process()
        self.observe(daemon, advance=0, cpu_time=100.0)
        self.observe(daemon, advance=1800, cpu_time=140.0)
        self.assertEqual(daemon.idle_seconds, 0)
        self.assertFalse(self.category.matcher(daemon))

    def test_busy_now_is_not_matched(self):
        daemon = process()
        self.observe(daemon, advance=0, cpu_time=100.0)
        self.observe(daemon, advance=1800, cpu_time=100.5, cpu=25.0)
        self.assertFalse(self.category.matcher(daemon))

    def test_gradle_daemon_keeps_its_threshold_and_is_not_matched(self):
        daemon = process(command=GRADLE)
        self.observe(daemon, advance=0, cpu_time=100.0)
        self.observe(daemon, advance=1800, cpu_time=107.0)
        self.assertEqual(daemon.idle_seconds, 0)
        daemon.idle_seconds = 7200
        self.assertFalse(self.category.matcher(daemon))


class KotlinIdleKillTests(unittest.TestCase):
    def test_idle_daemon_terminated_on_second_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [1_000_000.0]
            tracker = IdleTracker(str(Path(tmp) / "idle.json"), clock=lambda: now[0])
            daemon = process()

            def cycle(advance, cpu_time):
                now[0] += advance
                daemon.etime_seconds += int(advance)
                daemon.cpu_time_seconds = cpu_time
                killer = CategoryKiller(idle_tracker=tracker)
                with patch.object(killer.collector, "get_process_info", return_value=[daemon]), \
                        patch.object(killer, "_self_and_ancestors", return_value=set()), \
                        patch.object(killer, "_alive", return_value=False), \
                        patch("src.process_killer.category_killer.time.sleep"), \
                        patch("src.process_killer.category_killer.os.kill") as send:
                    return killer.kill_categories(["kotlin-idle"], quiet=True), send

            result, _ = cycle(0, 100.0)
            self.assertEqual(result["targeted"], 0)
            result, send = cycle(1800, 105.0)
            self.assertEqual(result["by_category"], {"kotlin-idle": 1})
            send.assert_called_once_with(daemon.pid, signal.SIGTERM)

    def test_daemon_schedules_kotlin_idle(self):
        self.assertIn("kotlin-idle", DEFAULT_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
