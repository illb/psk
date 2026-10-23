"""The standard selector copy in src/common must match kcli-lib, so kcli-lib's selector tests also cover it."""
import ast
import unittest
from pathlib import Path

COMMON = Path(__file__).resolve().parents[1] / "src" / "common"
KCLI = Path(__file__).resolve().parents[2] / "kcli" / "lib" / "src" / "lib" / "common"

VERBATIM = [
    "selector/config.py", "selector/item.py", "selector/prompt.py", "selector/selector.py",
    "style/__init__.py", "style/style.py", "style/theme.py",
    "policy/__init__.py", "policy/danger.py", "policy/nav.py", "policy/permission.py", "policy/policy.py",
    "browser/base/message_manager.py",
]


def _functions(path):
    src = path.read_text(encoding="utf-8")
    return {n.name: ast.get_source_segment(src, n)
            for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}


@unittest.skipUnless(KCLI.is_dir(), "kcli-lib checkout not found next to psk")
class CopyMatchesKcliLib(unittest.TestCase):
    def test_verbatim_files(self):
        for rel in VERBATIM:
            with self.subTest(rel=rel):
                self.assertEqual((COMMON / rel).read_text(encoding="utf-8"),
                                 (KCLI / rel).read_text(encoding="utf-8"),
                                 f"{rel} differs from kcli-lib — re-copy it")

    def test_prompt_utils_functions(self):
        ours, theirs = _functions(COMMON / "prompt_utils.py"), _functions(KCLI / "prompt_utils.py")
        self.assertTrue(ours)
        drifted = [name for name, body in ours.items() if body != theirs.get(name)]
        self.assertEqual(drifted, [], "functions differing from kcli-lib")


if __name__ == "__main__":
    unittest.main()
