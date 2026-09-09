import ctypes as c
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from src.process_killer import tail_output
from src.process_killer.categories import CATEGORY_BY_KEY, _is_orphan_tail, _tail_follows
from src.process_killer.category_killer import CategoryKiller
from src.process_killer.daemon import DEFAULT_CATEGORIES, _run_cycle
from src.process_killer.models import ProcessInfo


def proc(pid=900001, ppid="1", command="tail -f /tmp/example.log", stat="S"):
    return ProcessInfo(user="tester", pid=pid, ppid=ppid, cpu=0, mem=0, stat=stat,
                       start="00:00", uptime="1m", command=command, name="tail", type="tail")


class TailTests(unittest.TestCase):
    def test_options(self):
        positive = [
            "tail -f /tmp/example.log", "/usr/bin/tail -F /tmp/example.log",
            "tail -qf /tmp/example.log", "tail -Fn 10 /tmp/example.log",
            "tail -n 10 -f /tmp/example.log", "tail -fn10 /tmp/example.log",
            "tail -f -- -file", "tail --follow", "tail --follow=name",
            "tail --follow=descriptor --retry", "tail --lines=10 -f",
            "tail --bytes +10 -F", "tail -c10 -f", "tail -b 10 -f",
        ]
        negative = [
            "tail -- -f", "tail -- -file", "tail -n 20 /tmp/example.log",
            "tail example.log -f", "tail -n -f", "tail -fn10f", "tail -Fn",
            "tail --followed", "tail --follow=invalid", "tail -file",
            "tail -fr /tmp/example.log", "tail -f --unknown", "tail -f --bytes=bad",
            "tail --lines -f", "tail -n10f", "tail - /tmp/example.log -f",
            "sh -c 'tail -f /tmp/example.log'", "tail 'broken", "",
            "tail '/tmp/log -f'", "tail -frob", "tail --help -f",
        ]
        for command in positive + negative:
            with self.subTest(command=command):
                self.assertEqual(_tail_follows(command), command in positive)

    def test_match_and_identity(self):
        with patch("src.process_killer.categories.disconnected_tail_identity", return_value=(10, 20, 30)) as probe:
            target = proc()
            self.assertTrue(_is_orphan_tail(target))
            self.assertEqual(target.tail_identity, (10, 20, 30))
            probe.return_value = (11, 20, 30)
            self.assertFalse(_is_orphan_tail(target))
            probe.return_value = (10, 20, 31)
            self.assertFalse(_is_orphan_tail(target))
            probe.return_value = None
            self.assertFalse(_is_orphan_tail(target))
            probe.reset_mock()
            for target in (proc(ppid="2"), proc(stat="Z"), proc(command="tail -- -f")):
                self.assertFalse(_is_orphan_tail(target))
            probe.assert_not_called()

    def test_default_daemon_includes_tail(self):
        self.assertIn("orphan-tail", DEFAULT_CATEGORIES)
        with patch.object(CategoryKiller, "kill_categories", return_value={}) as kill:
            _run_cycle(DEFAULT_CATEGORIES, None, check_stale_ai=False)
            self.assertIn("orphan-tail", kill.call_args.args[0])

    def test_recheck_before_each_signal(self):
        target = proc()
        target.tail_identity = (10, 20, 30)
        module = "src.process_killer.categories.disconnected_tail_identity"
        with patch(module, return_value=None), patch("src.process_killer.category_killer.os.kill") as kill:
            self.assertEqual(CategoryKiller()._terminate([target], True, quiet=True), 0)
            kill.assert_not_called()
        with patch(module, side_effect=[(10, 20, 30), None]), \
                patch("src.process_killer.category_killer.os.kill") as kill, \
                patch("src.process_killer.category_killer.time.sleep"), \
                patch.object(CategoryKiller, "_alive", return_value=True):
            self.assertEqual(CategoryKiller()._terminate([target], True, quiet=True), 0)
            kill.assert_called_once_with(target.pid, signal.SIGTERM)

    def test_probe_fails_closed(self):
        with patch.object(tail_output, "_libproc", return_value=None):
            self.assertIsNone(tail_output.disconnected_tail_identity(900001))
        with patch.object(tail_output, "_libproc") as factory:
            for result in (0, -1, c.sizeof(tail_output._BSDInfo) - 1):
                factory.return_value.proc_pidinfo.return_value = result
                self.assertIsNone(tail_output.disconnected_tail_identity(900001))

    def test_kernel_fields_required(self):
        class Lib:
            def __init__(self, ppid=1, name=b"tail", peer=0, status=0x80, flags=2,
                         handle=3, changed=False, short_pipe=False):
                self.ppid, self.name, self.peer = ppid, name, peer
                self.status, self.flags, self.handle = status, flags, handle
                self.changed, self.short_pipe, self.calls = changed, short_pipe, 0

            def proc_pidinfo(self, pid, flavor, arg, output, size):
                self.calls += 1
                info = c.cast(output, c.POINTER(tail_output._BSDInfo)).contents
                info.pid, info.ppid, info.comm = pid, self.ppid, self.name
                info.start_sec = self.calls if self.changed else 1
                return size

            def proc_pidfdinfo(self, pid, fd, flavor, output, size):
                info = c.cast(output, c.POINTER(tail_output._PipeFDInfo)).contents
                info.file.openflags = self.flags
                info.pipe.peerhandle, info.pipe.status = self.peer, self.status
                info.pipe.handle = self.handle
                return size - 1 if self.short_pipe else size

        with patch.object(tail_output, "_libproc", return_value=Lib()):
            self.assertEqual(tail_output.disconnected_tail_identity(900001), (1, 0, 3))
        for kwargs in ({"ppid": 2}, {"name": b"sh"}, {"peer": 4}, {"status": 0},
                       {"flags": 1}, {"handle": 0}, {"changed": True}, {"short_pipe": True}):
            with self.subTest(kwargs=kwargs), patch.object(tail_output, "_libproc", return_value=Lib(**kwargs)):
                self.assertIsNone(tail_output.disconnected_tail_identity(900001))


@unittest.skipUnless(sys.platform == "darwin", "macOS libproc integration")
class TailIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="psk-tail-test-")
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "example.log"
        self.log.touch()
        self.orphans = []
        self.addCleanup(self.cleanup_orphans)

    def cleanup_orphans(self):
        for pid in self.orphans:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def orphan(self, output):
        code = (
            "import subprocess,sys; "
            "p=subprocess.Popen(['/usr/bin/tail','-f',sys.argv[1]], "
            "stdout=int(sys.argv[2]),stderr=subprocess.DEVNULL); print(p.pid)"
        )
        launch = subprocess.run([sys.executable, "-B", "-c", code, str(self.log), str(output)],
                                pass_fds=(output,), capture_output=True, text=True,
                                check=True, timeout=10)
        pid = int(launch.stdout.strip())
        self.orphans.append(pid)
        for _ in range(30):
            parent = subprocess.check_output(["ps", "-p", str(pid), "-o", "ppid="], text=True).strip()
            if parent == "1":
                return proc(pid=pid, command=f"/usr/bin/tail -f {self.log}")
            time.sleep(0.05)
        self.fail("fixture was not reparented")

    def test_active_reader_then_disconnect_and_terminate(self):
        read_fd, write_fd = os.pipe()
        duplicate = os.dup(read_fd)
        try:
            target = self.orphan(write_fd)
        finally:
            os.close(write_fd)
        try:
            with self.log.open("a") as stream:
                stream.write("active-output\n")
            ready, _, _ = select.select([read_fd], [], [], 5)
            self.assertTrue(ready)
            self.assertIn(b"active-output", os.read(read_fd, 4096))
            self.assertFalse(_is_orphan_tail(target))
            os.close(read_fd)
            read_fd = None
            self.assertFalse(_is_orphan_tail(target), "duplicate reader must be protected")
            os.close(duplicate)
            duplicate = None
            self.assertTrue(_is_orphan_tail(target), "disconnected stdout must be detected")
            killer = CategoryKiller()
            # Exercise the daemon path with collection restricted to this owned fixture.
            with patch.object(killer.collector, "get_process_info", return_value=[target]):
                preview = killer.find_category_targets(["orphan-tail"])
                self.assertEqual([p.pid for p, _ in preview], [target.pid])
                killer._print_targets(preview)
                result = killer.kill_categories(["orphan-tail"], quiet=True)
            self.assertEqual(result["killed"], 1)
            self.assertFalse(killer._alive(target.pid))
            self.orphans.remove(target.pid)
        finally:
            for fd in (read_fd, duplicate):
                if fd is not None:
                    os.close(fd)

    def test_file_null_and_terminal_protected(self):
        with tempfile.TemporaryFile() as output, open(os.devnull, "wb") as null:
            master, slave = pty.openpty()
            try:
                for fd in (output.fileno(), null.fileno(), slave):
                    target = self.orphan(fd)
                    self.assertFalse(_is_orphan_tail(target))
            finally:
                os.close(master)
                os.close(slave)

    def test_attached_disconnected_tail_protected(self):
        read_fd, write_fd = os.pipe()
        child = subprocess.Popen(["/usr/bin/tail", "-f", str(self.log)], stdout=write_fd,
                                 stderr=subprocess.DEVNULL)
        os.close(read_fd)
        os.close(write_fd)
        try:
            self.assertIsNone(tail_output.disconnected_tail_identity(child.pid))
            self.assertFalse(_is_orphan_tail(proc(pid=child.pid, ppid=str(os.getpid()))))
        finally:
            child.terminate()
            child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
