import unittest

from src.process_killer.categories import CATEGORY_BY_KEY
from src.process_killer.collector import ProcessCollector
from src.process_killer.models import ProcessInfo

DAY = 86400
BIN = "/home/user/.codex/packages/app-server-daemon/releases/0.1.0/bin/codex"


def process(pid, *, ppid="1", command, etime=20 * DAY, stat="Ss", live_children=0):
    return ProcessInfo(user="tester", pid=pid, ppid=ppid, cpu=0, mem=0, stat=stat,
                       start="00:00", uptime="1m", command=command, name="codex",
                       type="codex", etime_seconds=etime, live_children=live_children)


class CodexAppServerTests(unittest.TestCase):
    codex = CATEGORY_BY_KEY["codex"]

    def test_supervisor_with_live_server_is_not_a_leak(self):
        supervisor = process(920001, command=f"{BIN} app-server daemon pid-update-loop",
                             live_children=1)
        self.assertFalse(self.codex.matcher(supervisor))

    def test_supervisor_without_live_children_is_a_leak(self):
        supervisor = process(920001, command=f"{BIN} app-server daemon pid-update-loop")
        self.assertTrue(self.codex.matcher(supervisor))
        self.assertEqual(self.codex.reason(supervisor),
                         "orphaned app-server: PPID 1; no live children")

    def test_old_app_server_under_supervisor_is_not_stale(self):
        server = process(920002, ppid="920001", etime=5 * DAY, live_children=3,
                         command=f"{BIN} app-server --listen unix://")
        self.assertFalse(self.codex.matcher(server))

    def test_regular_codex_cli_rules_are_unchanged(self):
        orphan = process(920003, command="node /usr/lib/node_modules/@openai/codex/bin/codex.js",
                         etime=60, live_children=2)
        stale = process(920004, ppid="4242", command=f"{BIN} resume abc", etime=4 * DAY)
        recent = process(920005, ppid="4242", command=f"{BIN} resume abc", etime=60)
        self.assertTrue(self.codex.matcher(orphan))
        self.assertTrue(self.codex.matcher(stale))
        self.assertFalse(self.codex.matcher(recent))

    def test_live_children_ignores_zombies(self):
        parent = process(920010, command=f"{BIN} app-server daemon")
        alive = process(920011, ppid="920010", command=f"{BIN} app-server --listen unix://")
        zombie = process(920012, ppid="920010", command="<defunct>", stat="Z")
        lonely = process(920020, command=f"{BIN} app-server daemon")
        dead = process(920021, ppid="920020", command="<defunct>", stat="Z")
        ProcessCollector._count_live_children([parent, alive, zombie, lonely, dead])
        self.assertEqual(parent.live_children, 1)
        self.assertEqual(lonely.live_children, 0)


if __name__ == "__main__":
    unittest.main()
