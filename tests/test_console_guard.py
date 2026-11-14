import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
FACTORY_DIR = SRC / "common" / "console"
# prompt_utils.py must stay function-identical to kcli-lib (test_prompt_copy_drift).
KNOWN = {"common/prompt_utils.py"}
_CONSTRUCT = re.compile(r"\bConsole\(")


class ConsoleGuardTest(unittest.TestCase):
    def test_console_is_built_only_by_the_factory(self):
        offenders = {
            path.relative_to(SRC).as_posix()
            for path in SRC.rglob("*.py")
            if FACTORY_DIR not in path.parents
            and _CONSTRUCT.search(path.read_text(encoding="utf-8"))
        }
        self.assertEqual(sorted(offenders - KNOWN), [])


if __name__ == "__main__":
    unittest.main()
