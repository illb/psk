"""Highlighters that replace rich's default ReprHighlighter."""

from __future__ import annotations

import re

from rich.highlighter import Highlighter
from rich.text import Text

_URL = re.compile(r"\bhttps?://[^\s)\]>'\"]+")
_VALUE = r"""(?P<value>https?://[^\s)\]>'"]+|'[^']*'|"[^"]*"|[^\s,;)\]}]+)"""
# key=value anywhere; the key is one token (Hangul allowed).
_EQ_PAIR = re.compile(r"(?:(?<=^)|(?<=[\s(\[{,]))(?P<key>[\w.\-/]+)=(?!=)" + _VALUE, re.M)
# key: value only at the start of a line (after indent or a "-", "*", "|" bullet), key of 1-3 words,
# so prose like "조회 실패: HTTP 503", times (12:30) and schemes (http:) are left alone.
_COLON_PAIR = re.compile(
    r"^[ \t]*(?:[-*|][ \t]+)?(?P<key>[\w.\-/]+(?: [\w.\-/]+){0,2}):[ ]+" + _VALUE, re.M
)


class DataHighlighter(Highlighter):
    """key=value pairs anywhere and line-leading key: value pairs. Nothing else is highlighted."""

    def highlight(self, text: Text) -> None:
        plain = text.plain
        # Already-rendered ANSI must pass through untouched.
        if "\x1b" in plain:
            return
        urls = [m.span() for m in _URL.finditer(plain)]
        for pattern in (_EQ_PAIR, _COLON_PAIR):
            for match in pattern.finditer(plain):
                if any(start < match.start("key") < end for start, end in urls):
                    continue
                text.stylize("data.key", *match.span("key"))
                text.stylize("data.value", *match.span("value"))


class MinimalHighlighter(Highlighter):
    """URLs only."""

    def highlight(self, text: Text) -> None:
        plain = text.plain
        if "\x1b" in plain:
            return
        for match in _URL.finditer(plain):
            text.stylize("data.url", match.start(), match.end())
