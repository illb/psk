"""unittest port of kcli-lib tests/common/test_console.py for the copied console module."""

import io
import os
import re
import unittest
from unittest import mock

from rich.console import Console
from rich.text import Text

from src.common.console import (
    ANSI_REPRINT,
    HIGHLIGHT_MODES,
    REPR_HIGHLIGHT,
    check_ansi,
    guard_console_prints,
    make_console,
    print_ansi,
    strip_ansi,
)
from src.common.console.samples import ANSI_SAMPLE, ANSI_SAMPLE_PLAIN, SAMPLES


def _render(mode, message, *, markup=True):
    console = make_console(
        mode=mode, file=io.StringIO(), force_terminal=True, width=300
    )
    with console.capture() as captured:
        console.print(message, markup=markup)
    return captured.get()


def _rich_default(message, *, markup=True):
    console = Console(
        file=io.StringIO(), force_terminal=True, width=300, color_system="256"
    )
    with console.capture() as captured:
        console.print(message, markup=markup)
    return captured.get()


def _spans(rendered):
    return re.findall(r"\x1b\[([0-9;]+)m([^\x1b]*)\x1b\[0m", rendered)


class ConsoleTest(unittest.TestCase):
    def test_every_mode_keeps_visible_text(self):
        for mode in HIGHLIGHT_MODES:
            for sample in SAMPLES:
                with self.subTest(mode=mode, sample=sample.name):
                    self.assertEqual(
                        check_ansi(_render(mode, sample.markup), sample.plain), []
                    )
                    self.assertEqual(
                        check_ansi(_render(mode, sample.marked), sample.plain), []
                    )

    def test_basic_adds_nothing_beyond_markup(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample.name):
                expected = _render("basic", Text.from_markup(sample.markup))
                self.assertEqual(_render("basic", sample.markup), expected)

    def test_data_marks_equals_pairs(self):
        spans = _spans(_render("data", "config=/etc/app.yaml dryRun=True owner=None"))
        self.assertEqual(
            spans,
            [
                ("1", "config"),
                ("36", "/etc/app.yaml"),
                ("1", "dryRun"),
                ("36", "True"),
                ("1", "owner"),
                ("36", "None"),
            ],
        )

    def test_data_marks_colon_pairs_only_at_line_start(self):
        spans = _spans(_render("data", "환경: production 비교 8개: 일치 8, 어긋남 0"))
        self.assertIn(("1", "환경"), spans)
        self.assertIn(("36", "production"), spans)
        self.assertNotIn(("1", "8개"), spans)

    def test_data_colon_key_may_have_up_to_three_words(self):
        spans = _spans(_render("data", "  - Grafana URL: https://x.example/d?a=1"))
        self.assertEqual(
            spans, [("1", "Grafana URL"), ("36", "https://x.example/d?a=1")]
        )

    def test_data_ignores_colons_inside_prose(self):
        self.assertEqual(
            _render("data", "✗ 조회 실패: HTTP 503"), "✗ 조회 실패: HTTP 503\n"
        )

    def test_data_keeps_url_whole_and_ignores_pairs_inside_it(self):
        spans = _spans(_render("data", "url=https://x.example/d?var-a=1&b=2 done"))
        self.assertEqual(
            spans, [("1", "url"), ("36", "https://x.example/d?var-a=1&b=2")]
        )

    def test_data_ignores_times_schemes_and_double_equals(self):
        rendered = _render(
            "data", "at 12:30 see http://x a==b ns:pod 3회 느림(대기) 20,000 80%"
        )
        self.assertNotIn("\x1b[", rendered.replace("\x1b[0m", ""))

    def test_data_ignores_values_and_numbers_without_a_key(self):
        self.assertEqual(
            _render("data", "값 1,000 넘음 (총 3건) True"),
            "값 1,000 넘음 (총 3건) True\n",
        )

    def test_minimal_marks_url_only(self):
        spans = _spans(_render("minimal", "a=1 see https://x.example/a?b=1 now"))
        self.assertEqual(spans, [("4", "https://x.example/a?b=1")])

    def test_rich_default_breaks_reprinted_ansi(self):
        self.assertNotEqual(
            check_ansi(_rich_default(ANSI_SAMPLE, markup=False), ANSI_SAMPLE_PLAIN), []
        )

    def test_reprinted_ansi_passes_through(self):
        for mode in HIGHLIGHT_MODES:
            with self.subTest(mode=mode):
                rendered = _render(mode, ANSI_SAMPLE, markup=False)
                self.assertEqual(check_ansi(rendered, ANSI_SAMPLE_PLAIN), [])

    def test_print_ansi_keeps_codes_and_text(self):
        console = make_console(mode="data", file=io.StringIO(), force_terminal=True)
        with console.capture() as captured:
            print_ansi(console, ANSI_SAMPLE)
        self.assertEqual(strip_ansi(captured.get()).rstrip("\n"), ANSI_SAMPLE_PLAIN)
        self.assertEqual(check_ansi(captured.get(), ANSI_SAMPLE_PLAIN), [])

    def test_no_color_env_is_respected(self):
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            console = make_console(mode="data", file=io.StringIO(), force_terminal=True)
            with console.capture() as captured:
                console.print("[green]2/2 done[/green]")
        self.assertNotIn("\x1b[3", captured.get())

    def test_check_ansi_reports_broken_escape(self):
        self.assertNotEqual(check_ansi("\x1b\x1b[1m[\x1b[0m38;5;208m x"), [])

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            make_console(mode="repr")

    def test_guard_records_violations_without_a_tty(self):
        with guard_console_prints() as violations:
            Console(file=io.StringIO()).print("[green]2/2 done[/green]")
            Console(file=io.StringIO(), highlight=False).print(ANSI_SAMPLE)
            make_console(file=io.StringIO()).print("[ok]2/2 done[/ok]")
            print_ansi(make_console(file=io.StringIO()), ANSI_SAMPLE)
        self.assertEqual([v.kind for v in violations], [REPR_HIGHLIGHT, ANSI_REPRINT])


if __name__ == "__main__":
    unittest.main()
