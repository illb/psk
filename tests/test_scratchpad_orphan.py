import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_killer.categories import CATEGORY_BY_KEY
from src.process_killer.category_killer import CategoryKiller
from src.process_killer.claude_sessions import live_claude_session_ids
from src.process_killer.daemon import DEFAULT_CATEGORIES
from src.process_killer.idle_tracker import IdleTracker
from src.process_killer.models import ProcessInfo

SESSION = "8854f0f3-7e82-4f67-91c2-7f3975ec8483"
HARNESS = ("/opt/jdk/bin/java -Xmx512m -cp /private/tmp/claude-501/-Users-me-proj/"
           f"{SESSION}/scratchpad/xd5/snapA/tool MhrHarness fake")


def process(pid=950001, *, ppid="1", command=HARNESS, cpu=0.0, cpu_time=345.0, idle=None):
    proc = ProcessInfo(user="tester", pid=pid, ppid=ppid, cpu=cpu, mem=0, stat="S",
                       start="00:00", uptime="24d", command=command, name="java",
                       type="java", etime_seconds=24 * 86400, cpu_time_seconds=cpu_time)
    proc.idle_seconds = idle
    return proc


def live(ids):
    return patch("src.process_killer.categories.live_claude_session_ids", return_value=ids)


class ScratchpadOrphanMatcherTests(unittest.TestCase):
    category = CATEGORY_BY_KEY["scratchpad-orphan"]

    def test_idle_orphan_of_ended_session_matches(self):
        proc = process(idle=3600)
        with live({"another-session"}):
            self.assertTrue(self.category.matcher(proc))
        self.assertEqual(self.category.reason(proc), "PPID 1; session 8854f0f3 ended; idle 60m")

    def test_guards(self):
        cases = {
            "session still running": (process(idle=7200), {SESSION}),
            "registry unreadable": (process(idle=7200), None),
            "parent alive": (process(idle=7200, ppid="4242"), set()),
            "not idle long enough": (process(idle=3599), set()),
            "idle unknown": (process(idle=None), set()),
            "busy now": (process(idle=7200, cpu=30.0), set()),
            "outside scratchpad": (process(idle=7200, command=HARNESS.replace("/scratchpad/", "/tasks/")), set()),
        }
        for name, (proc, ids) in cases.items():
            with self.subTest(name), live(ids):
                self.assertFalse(self.category.matcher(proc))


class LiveSessionIdsTests(unittest.TestCase):
    def test_pid_and_start_time_must_match(self):
        own_start = subprocess.run(["ps", "-o", "lstart=", "-p", str(os.getpid())], capture_output=True,
                                   text=True, env={**os.environ, "TZ": "UTC"}).stdout.strip()
        with tempfile.TemporaryDirectory() as tmp:
            entries = {
                "alive": {"pid": os.getpid(), "sessionId": "alive", "procStart": own_start},
                "reused": {"pid": os.getpid(), "sessionId": "reused", "procStart": "Mon Jan  1 00:00:00 2001"},
                "dead": {"pid": 999_999, "sessionId": "dead", "procStart": own_start},
            }
            for name, data in entries.items():
                Path(tmp, f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
            Path(tmp, "broken.json").write_text("{", encoding="utf-8")
            self.assertEqual(live_claude_session_ids(tmp), {"alive"})

    def test_missing_registry_is_unknown(self):
        self.assertIsNone(live_claude_session_ids("/nonexistent/claude/sessions"))


class ScratchpadOrphanKillTests(unittest.TestCase):
    def test_tracked_across_cycles_then_terminated(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [1_000_000.0]
            tracker = IdleTracker(str(Path(tmp) / "idle.json"), clock=lambda: now[0])
            orphan = process()

            def cycle(advance):
                now[0] += advance
                orphan.etime_seconds += int(advance)
                killer = CategoryKiller(idle_tracker=tracker)
                with patch.object(killer.collector, "get_process_info", return_value=[orphan]), \
                        patch.object(killer, "_self_and_ancestors", return_value=set()), \
                        patch.object(killer, "_alive", return_value=False), \
                        patch("src.process_killer.category_killer.time.sleep"), \
                        patch("src.process_killer.category_killer.os.kill") as send, \
                        live(set()):
                    return killer.kill_categories(["scratchpad-orphan"], quiet=True), send

            result, _ = cycle(0)
            self.assertEqual(result["targeted"], 0)
            result, _ = cycle(1800)
            self.assertEqual(result["targeted"], 0)
            result, send = cycle(1800)
            self.assertEqual(result["by_category"], {"scratchpad-orphan": 1})
            send.assert_called_once_with(orphan.pid, signal.SIGTERM)

    def test_daemon_schedules_scratchpad_orphan(self):
        self.assertIn("scratchpad-orphan", DEFAULT_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
