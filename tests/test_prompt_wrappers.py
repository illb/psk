"""questionary_utils wrappers over the standard selector: number quick-select, toggles, empty selection, cancel."""
import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from src.common import questionary_utils as q
from src.common.exceptions import CancelledError
from src.common.selector import Selector

CHOICES = [("a", "alpha"), ("b", "beta"), ("c", "gamma")]


def _keys(keys, fn, *args, **kwargs):
    with create_pipe_input() as inp:
        inp.send_text(keys)
        with create_app_session(input=inp, output=DummyOutput()):
            return fn(*args, **kwargs)


class InteractiveWrappers(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(Selector, "_is_interactive_terminal", staticmethod(lambda: True))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_select_single_number_quick_select(self):
        self.assertEqual(_keys("2", q.select_single, "Pick", CHOICES), "b")

    def test_select_single_q_raises_cancelled(self):
        with self.assertRaises(CancelledError):
            _keys("q", q.select_single, "Pick", CHOICES)

    def test_select_checkbox_numbers_toggle(self):
        self.assertEqual(_keys("13\r", q.select_checkbox, "Pick", CHOICES), ["a", "c"])

    def test_select_checkbox_allows_empty_selection(self):
        self.assertEqual(_keys("\r", q.select_checkbox, "Pick", CHOICES), [])

    def test_select_checkbox_keeps_pre_checked_values(self):
        self.assertEqual(_keys("\r", q.select_checkbox, "Pick", CHOICES, checked_values=["b"]), ["b"])

    def test_select_checkbox_q_raises_cancelled(self):
        with self.assertRaises(CancelledError):
            _keys("q", q.select_checkbox, "Pick", CHOICES)

    def test_select_yes_no(self):
        self.assertIs(_keys("1", q.select_yes_no, "Proceed?", default=False), True)
        self.assertIs(_keys("2", q.select_yes_no, "Proceed?", default=True), False)
        self.assertIs(_keys("\r", q.select_yes_no, "Proceed?", default=True), True)
        self.assertIsNone(_keys("q", q.select_yes_no, "Proceed?", raise_on_cancel=False))


class NonInteractiveWrappers(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(Selector, "_is_interactive_terminal", staticmethod(lambda: False))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exits_2_without_prompting(self):
        for ask in (lambda: q.select_single("Pick", CHOICES),
                    lambda: q.select_checkbox("Pick", CHOICES),
                    lambda: q.select_yes_no("Proceed?")):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                ask()
            self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
