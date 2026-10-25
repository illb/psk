import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.process_killer.categories import CATEGORY_BY_KEY, LSP_OVERSIZE_KB
from src.process_killer.category_killer import CategoryKiller
from src.process_killer.daemon import DEFAULT_CATEGORIES
from src.process_killer.idle_tracker import IdleTracker
from src.process_killer.models import ProcessInfo

KOTLIN_LS = ("/home/user/.serena/language_servers/static/KotlinLanguageServer/"
             "kotlin_language_server/jre/bin/java -cp ls.jar org.javacs.kt.MainKt")


def process(pid=930001, *, ppid="4242", command=KOTLIN_LS, cpu=0.0, cpu_time=900.0,
            etime=86400, idle=None):
    proc = ProcessInfo(user="tester", pid=pid, ppid=ppid, cpu=cpu, mem=0, stat="S",
                       start="00:00", uptime="1d", command=command, name="java",
                       type="java", etime_seconds=etime, cpu_time_seconds=cpu_time)
    proc.idle_seconds = idle
    return proc


def footprint(kb):
    return patch("src.process_killer.categories.footprint_kb", return_value=kb)


class LspOversizeMatcherTests(unittest.TestCase):
    category = CATEGORY_BY_KEY["lsp-oversize"]

    def test_oversized_idle_serena_ls_matches(self):
        proc = process(idle=1800)
        with footprint(int(4.2 * 1024 * 1024)):
            self.assertTrue(self.category.matcher(proc))
        self.assertEqual(self.category.reason(proc), "footprint 4.2G >= 3G; idle 30m")

    def test_guards(self):
        big = int(4.2 * 1024 * 1024)
        cases = {
            "small": (process(idle=3600), LSP_OVERSIZE_KB - 1),
            "not idle long enough": (process(idle=1799), big),
            "idle unknown": (process(idle=None), big),
            "busy now": (process(idle=3600, cpu=40.0), big),
            "orphan belongs to lsp": (process(idle=3600, ppid="1"), big),
            "not serena": (process(idle=3600, command="/usr/bin/java org.javacs.kt.MainKt"), big),
            "footprint unavailable": (process(idle=3600), None),
        }
        for name, (proc, kb) in cases.items():
            with self.subTest(name), footprint(kb):
                self.assertFalse(self.category.matcher(proc))


class LspOversizeKillTests(unittest.TestCase):
    def test_tracked_across_cycles_then_terminated(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [1_000_000.0]
            tracker = IdleTracker(str(Path(tmp) / "idle.json"), clock=lambda: now[0])
            ls = process(idle=None)

            def cycle(advance):
                now[0] += advance
                ls.etime_seconds += int(advance)
                killer = CategoryKiller(idle_tracker=tracker)
                with patch.object(killer.collector, "get_process_info", return_value=[ls]), \
                        patch.object(killer, "_self_and_ancestors", return_value=set()), \
                        patch.object(killer, "_alive", return_value=False), \
                        patch("src.process_killer.category_killer.time.sleep"), \
                        patch("src.process_killer.category_killer.os.kill") as send, \
                        footprint(4 * 1024 * 1024):
                    return killer.kill_categories(["lsp-oversize"], quiet=True), send

            result, send = cycle(0)
            self.assertEqual(result["targeted"], 0)
            result, send = cycle(1800)
            self.assertEqual(result["by_category"], {"lsp-oversize": 1})
            send.assert_called_once_with(ls.pid, signal.SIGTERM)

    def test_daemon_schedules_lsp_oversize(self):
        self.assertIn("lsp-oversize", DEFAULT_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
