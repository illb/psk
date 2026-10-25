import errno
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from src.process_killer.categories import CATEGORY_BY_KEY
from src.process_killer.category_killer import CategoryKiller
from src.process_killer.daemon import _run_cycle
from src.process_killer.models import ProcessInfo


def process(pid=900001, ppid="1", stat="S", command="gopls --token=secret /workspace/private"):
    return ProcessInfo(user="tester", pid=pid, ppid=ppid, cpu=0, mem=0,
                       stat=stat, start="00:00", uptime="1m", command=command,
                       name="test", type="test")


class SignalAuditTests(unittest.TestCase):
    def test_gradle_exclusion_and_active_build_are_audited(self):
        events = []
        killer = CategoryKiller(audit=events.append)
        wrapper = process(command="java org.gradle.wrapper.GradleWrapperMain test")
        active = process(900002, str(wrapper.pid), command="java org.gradle.launcher.daemon.bootstrap.GradleDaemon")
        idle = process(900003, command="java org.gradle.launcher.daemon.bootstrap.GradleDaemon")
        with patch.object(killer.collector, "get_process_info", return_value=[wrapper, active, idle]), \
                patch.object(killer, "_self_and_ancestors", return_value=set()), \
                patch("src.process_killer.category_killer.os.kill") as send:
            result = killer.kill_categories(["zombie", "lsp", "orphan-tail"], quiet=True)
        send.assert_not_called()
        self.assertEqual(result["targeted"], 0)
        decisions = [e for e in events if e["event"] == "gradle-decision"]
        self.assertEqual(len(decisions), 3)
        self.assertTrue(all(not e["selected"] for e in decisions))
        self.assertEqual({e["process_pid"] for e in events if e["event"] == "protected"},
                         {wrapper.pid, active.pid})

    def test_manual_gradle_selection_is_not_reported_as_excluded(self):
        events = []
        killer = CategoryKiller(audit=events.append)
        idle = process(command="java org.gradle.launcher.daemon.bootstrap.GradleDaemon")
        with patch.object(killer.collector, "get_process_info", return_value=[idle]), \
                patch.object(killer, "_self_and_ancestors", return_value=set()):
            targets = killer.find_category_targets(["gradle"])
        self.assertEqual(len(targets), 1)
        self.assertTrue(events[-1]["selected"])

    def test_zombie_is_not_counted_as_killed(self):
        events = []
        killer = CategoryKiller(audit=events.append)
        zombies = [process(stat="Z"), process(900002, "900010", "Z"),
                   process(900003, "900010", "Z")]
        with patch("src.process_killer.category_killer.os.kill") as send:
            result = killer._execute([(p, CATEGORY_BY_KEY["zombie"]) for p in zombies], True, quiet=True)
        self.assertEqual(result["killed"], 0)
        self.assertEqual(result["reap_signals"], 1)
        self.assertEqual(result["targeted"], 3)
        send.assert_called_once_with(900010, signal.SIGCHLD)
        self.assertEqual(sum(e.get("outcome") == "sent" for e in events), 1)
        self.assertTrue(any(e.get("reason") == "init-parent" for e in events))
        self.assertEqual({e["process_pid"] for e in events if e["event"] == "selected"},
                         {900001, 900002, 900003})

    def test_term_and_force_audit_without_arguments(self):
        events = []
        target = process()
        killer = CategoryKiller(audit=events.append)
        with patch("src.process_killer.category_killer.os.kill") as send, \
                patch("src.process_killer.category_killer.time.sleep"), \
                patch.object(killer, "_alive", side_effect=[True, False]):
            result = killer._execute([(target, CATEGORY_BY_KEY["lsp"])], True, quiet=True)
        self.assertEqual(result["killed"], 1)
        self.assertEqual([call.args[1] for call in send.call_args_list], [signal.SIGTERM, signal.SIGKILL])
        self.assertEqual([e["signal"] for e in events if e.get("outcome") == "sent"],
                         ["SIGTERM", "SIGKILL"])
        self.assertEqual(events[-1]["alive"], False)
        self.assertTrue(all(e["category"] == "lsp" for e in events))
        self.assertNotIn("secret", json.dumps(events))
        self.assertNotIn("/workspace/private", json.dumps(events))
        self.assertNotIn("tester", json.dumps(events))

    def test_signal_error_is_logged(self):
        events = []
        with patch("src.process_killer.category_killer.os.kill", side_effect=PermissionError(errno.EPERM, "denied")):
            result = CategoryKiller(audit=events.append)._execute(
                [(process(), CATEGORY_BY_KEY["lsp"])], True, quiet=True)
        self.assertEqual(result["killed"], 0)
        self.assertEqual(events[-1]["outcome"], "error")
        self.assertEqual(events[-1]["errno"], errno.EPERM)
        self.assertFalse(any(e.get("outcome") == "sent" for e in events))

    def test_tail_recheck_skip_is_logged(self):
        events = []
        target = process(command="tail -f /tmp/example.log")
        target.tail_identity = (1, 2, 3)
        with patch("src.process_killer.categories.disconnected_tail_identity", return_value=None), \
                patch("src.process_killer.category_killer.os.kill") as send:
            result = CategoryKiller(audit=events.append)._execute(
                [(target, CATEGORY_BY_KEY["orphan-tail"])], True, quiet=True)
        self.assertEqual(result["killed"], 0)
        self.assertEqual(events[-1]["reason"], "tail-recheck-failed")
        send.assert_not_called()

    def test_daemon_writes_audit_and_correct_summary(self):
        with tempfile.TemporaryDirectory() as tmp, patch("src.process_killer.daemon.CategoryKiller") as factory:
            path = Path(tmp) / "daemon.log"
            def run(*args, **kwargs):
                factory.call_args.kwargs["audit"]({"event": "signal", "target_pid": 900001,
                                                    "signal": "SIGCHLD", "outcome": "sent"})
                return {"targeted": 1, "killed": 0, "reap_signals": 1, "by_category": {"zombie": 1}}
            factory.return_value.kill_categories.side_effect = run
            _run_cycle(["zombie"], path, check_stale_ai=False)
            lines = path.read_text().splitlines()
            records = [json.loads(line.split("audit ", 1)[1]) for line in lines if "audit " in line]
            event = records[1]
            self.assertEqual(event["target_pid"], 900001)
            self.assertEqual(records[0]["event"], "cycle-start")
            self.assertEqual(records[-1]["event"], "cycle-end")
            self.assertEqual(records[-1]["signals"]["sent"], 1)
            self.assertEqual(len({e["cycle_id"] for e in records}), 1)
            self.assertIn("killed=0 targeted=1 reap_signals=1 [zombie=1]", lines[-1])

    def test_unwritable_audit_log_prevents_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp, patch("src.process_killer.daemon.CategoryKiller") as factory:
            _run_cycle(["zombie"], Path(tmp), check_stale_ai=False)
        factory.assert_not_called()

    def test_signal_audit_failure_stops_before_sending(self):
        def audit(event):
            if event["event"] == "signal":
                raise RuntimeError("audit log write failed")
        with patch("src.process_killer.category_killer.os.kill") as send:
            with self.assertRaises(RuntimeError):
                CategoryKiller(audit=audit)._execute(
                    [(process(), CATEGORY_BY_KEY["lsp"])], True, quiet=True)
        send.assert_not_called()

    def test_failed_cycle_has_no_complete_record(self):
        with tempfile.TemporaryDirectory() as tmp, patch("src.process_killer.daemon.CategoryKiller") as factory:
            path = Path(tmp) / "daemon.log"
            factory.return_value.kill_categories.side_effect = RuntimeError("private detail")
            _run_cycle(["zombie"], path, check_stale_ai=False)
            output = path.read_text()
        self.assertIn("cycle error:", output)
        self.assertNotIn("cycle-end", output)
        self.assertNotIn("private detail", output)


if __name__ == "__main__":
    unittest.main()
