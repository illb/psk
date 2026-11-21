import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.process_killer import gradle_build
from src.process_killer.categories import CATEGORY_BY_KEY, _stuck_build_reason
from src.process_killer.daemon import DEFAULT_CATEGORIES
from src.process_killer.gradle_build import Build, app_children, current_build, daemon_log, workers_busy
from src.process_killer.models import ProcessInfo

GRADLE = "/opt/jdk/bin/java -Xmx512m org.gradle.launcher.daemon.bootstrap.GradleDaemon 9.5.0"
KOTLIN = "/opt/jdk/bin/java org.jetbrains.kotlin.daemon.KotlinCompileDaemon --daemon-runFilesPath x"
START = "2026-11-20T23:28:39.757+0900"
STARTED = datetime.strptime(START, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()


def start_line(ts=START):
    return (f"{ts} [INFO] [org.gradle.launcher.daemon.server.exec.StartBuildOrRespondWithBusy] "
            "Daemon is about to start building Build{id=2c25fc05, currentDir=/repo}. Dispatching build started information...\n")


EXHAUSTED = "The Daemon will expire after the build after running out of JVM Metaspace.\n"


def process(*, command=GRADLE, etime=10 * 3600):
    return ProcessInfo(user="tester", pid=83228, ppid="1", cpu=300.0, mem=0, stat="R",
                       start="00:00", uptime="10h", command=command, name="java",
                       type="java", etime_seconds=etime)


class CurrentBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "daemon-83228.out.log"

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, *lines):
        self.log.write_text("2026-11-20T23:28:39.655+0900 [DEBUG] [DaemonMain] start\n" + "".join(lines))
        return current_build(self.log)

    def test_started_build_without_result_is_running(self):
        self.assertEqual(self.read(start_line(), "> Task :compileKotlin\n"), Build(STARTED))

    def test_reported_result_ends_the_build(self):
        self.assertIsNone(self.read(start_line(), "BUILD SUCCESSFUL in 1m 19s\n"))
        self.assertIsNone(self.read(start_line(), "BUILD FAILED in 307ms\n"))

    def test_daemon_finish_line_ends_a_tooling_api_build(self):
        finished = ("2026-11-21T00:00:00.000+0900 [DEBUG] [org.gradle.launcher.daemon.server.exec.ExecuteBuild] "
                    "The daemon has finished executing the build.\n")
        self.assertIsNone(self.read(start_line(), finished))

    def test_build_output_quoting_the_markers_does_not_end_the_build(self):
        self.assertEqual(self.read(start_line(), "  > BUILD SUCCESSFUL in 2s (from a nested build)\n"),
                         Build(STARTED))

    def test_memory_exhaustion_is_recorded_on_the_running_build(self):
        self.assertEqual(self.read(start_line(), "java.lang.OutOfMemoryError: Metaspace\n", EXHAUSTED),
                         Build(STARTED, "Metaspace"))

    def test_only_the_last_build_counts(self):
        later = "2026-11-21T01:00:00.000+0900"
        build = self.read(start_line(), EXHAUSTED, "BUILD FAILED in 3m\n", start_line(later))
        self.assertEqual(build, Build(datetime.strptime(later, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()))

    def test_missing_log_is_unknown(self):
        self.assertIsNone(current_build(self.log))


class StuckReasonTests(unittest.TestCase):
    category = CATEGORY_BY_KEY["gradle-stuck"]

    def reason(self, build, *, apps=(), busy=False, proc=None, running=None):
        proc = proc or process()
        now = STARTED + running
        with patch("src.process_killer.categories.daemon_log", return_value=Path("/x.log")), \
                patch("src.process_killer.categories.current_build", return_value=build), \
                patch("src.process_killer.categories.app_children", return_value=list(apps)), \
                patch("src.process_killer.categories.workers_busy", return_value=busy):
            return _stuck_build_reason(proc, now)

    def test_build_over_an_hour_is_stuck(self):
        self.assertEqual(self.reason(Build(STARTED), running=3600 + 60), "build running 1h 1m")

    def test_build_under_an_hour_is_kept(self):
        self.assertIsNone(self.reason(Build(STARTED), running=3600 - 60))

    def test_build_with_busy_test_workers_is_kept(self):
        self.assertIsNone(self.reason(Build(STARTED), running=6 * 3600, busy=True))

    def test_build_running_an_app_is_kept(self):
        self.assertIsNone(self.reason(Build(STARTED), running=6 * 3600,
                                      apps=["/opt/jdk/bin/java -cp app.jar com.example.MainKt"]))

    def test_memory_exhausted_build_is_stuck_after_thirty_minutes_even_with_an_app(self):
        build = Build(STARTED, "Metaspace")
        self.assertIsNone(self.reason(build, running=29 * 60))
        self.assertEqual(self.reason(build, running=31 * 60, apps=["java -cp app.jar Main"]),
                         "build 31m, daemon out of JVM Metaspace")

    def test_log_from_an_earlier_process_with_the_same_pid_is_ignored(self):
        self.assertIsNone(self.reason(Build(STARTED), running=5 * 3600, proc=process(etime=3600)))

    def test_no_running_build_is_kept(self):
        self.assertIsNone(self.reason(None, running=5 * 3600))

    def test_kotlin_daemon_is_not_a_gradle_build(self):
        self.assertIsNone(self.reason(Build(STARTED), running=5 * 3600, proc=process(command=KOTLIN)))

    def test_matcher_keeps_the_reason_for_the_audit(self):
        proc = process()
        with patch("src.process_killer.categories._stuck_build_reason", return_value="build running 9h 0m"):
            self.assertTrue(self.category.matcher(proc))
        self.assertEqual(self.category.reason(proc), "build running 9h 0m")

    def test_daemon_runs_gradle_stuck_by_default(self):
        self.assertIn("gradle-stuck", DEFAULT_CATEGORIES)


def completed(stdout):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


class ProcessLookupTests(unittest.TestCase):
    def test_app_children_skip_build_workers(self):
        ps = ("  83228 0:10.00 /opt/jdk/bin/java -cp w.jar worker.org.gradle.process.internal.worker.GradleWorkerMain 'Gradle Test Executor 3'\n"
              "  83228 0:02.00 /opt/jdk/bin/java org.jetbrains.kotlin.daemon.KotlinCompileDaemon\n"
              "  83228 1:00.00 /opt/jdk/bin/java -cp app.jar com.example.MainKt\n"
              "  99999 0:00.10 /opt/jdk/bin/java -cp other.jar Other\n")
        with patch.object(gradle_build.subprocess, "run", return_value=completed(ps)):
            self.assertEqual(app_children(83228), ["/opt/jdk/bin/java -cp app.jar com.example.MainKt"])

    def test_app_children_protect_when_ps_fails(self):
        with patch.object(gradle_build.subprocess, "run", side_effect=OSError):
            self.assertTrue(app_children(83228))

    def test_workers_busy_compares_worker_cpu_over_the_window(self):
        def ps(worker_cpu, app_cpu):
            return completed(f"  83228 {worker_cpu} /opt/jdk/bin/java worker.org.gradle.process.internal.worker.GradleWorkerMain\n"
                             f"  83228 {app_cpu} /opt/jdk/bin/java -cp app.jar Main\n"
                             f"  77777 99:00.00 /opt/jdk/bin/java worker.org.gradle.process.internal.worker.GradleWorkerMain\n")
        cases = [((ps("1:00.00", "0:01.00"), ps("1:02.50", "0:01.00")), True),
                 ((ps("1:00.00", "0:01.00"), ps("1:00.30", "9:00.00")), False),
                 ((ps("1:59:00.00", "0:00.00"), ps("2:00:00.00", "0:00.00")), True)]
        for samples, expected in cases:
            with patch.object(gradle_build.subprocess, "run", side_effect=list(samples)), \
                    patch.object(gradle_build.time, "sleep"):
                self.assertEqual(workers_busy(83228), expected)

    def test_workers_busy_protects_when_ps_fails(self):
        with patch.object(gradle_build.subprocess, "run", side_effect=OSError), \
                patch.object(gradle_build.time, "sleep"):
            self.assertTrue(workers_busy(83228))

    def test_daemon_log_comes_from_the_open_file(self):
        lsof = "p83228\nf1\nn/custom/home/daemon/9.5.0/daemon-83228.out.log\nf2\nn/dev/null\n"
        with patch.object(gradle_build.subprocess, "run", return_value=completed(lsof)):
            self.assertEqual(daemon_log(83228), Path("/custom/home/daemon/9.5.0/daemon-83228.out.log"))


if __name__ == "__main__":
    unittest.main()
