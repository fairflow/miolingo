"""Unit tests for the shared (source, target) header parser.

Covers the canonical forms found in language-material files and vocab
imports, plus negative cases that must NOT be matched so real data rows
are never mis-classified as headers.
"""
from __future__ import annotations

import pytest

from import_header import HEADER_RE, is_header_line, parse_header


# ── positive: various well-formed headers ────────────────────────────────
@pytest.mark.parametrize("line", [
    "(fr, en)",
    "(pt, en)",
    "(en, fr)",
    "# (pt, en)",
    "  (pt, en)  ",
    "( FR , EN )",         # whitespace + uppercase
    "(nl,de)",             # no spaces
    "(por, eng)",          # 3-letter codes accepted
])
def test_is_header_line_accepts(line):
    assert is_header_line(line) is True


# ── negative: data rows and malformed tuples must NOT match ───────────────
@pytest.mark.parametrize("line", [
    "",
    "hello",
    "# Some comment",
    "bonjour | hello",
    "bonjour | hello | [bɔ̃ʒuʁ]",
    "(fr,en,de)",          # three codes
    "(fr)",                # one code
    "fr, en",              # no parens
    "(fr, en) extra",      # trailing junk
    "(1r, en)",            # digit in code
    "(pt-br, en)",         # hyphen not allowed
])
def test_is_header_line_rejects(line):
    assert is_header_line(line) is False


# ── parse_header returns lowercased codes ─────────────────────────────────
def test_parse_header_basic():
    assert parse_header("(fr, en)") == ("fr", "en")


def test_parse_header_case_insensitive():
    assert parse_header("( PT , EN )") == ("pt", "en")


def test_parse_header_commented():
    assert parse_header("# (pt, en)") == ("pt", "en")


def test_parse_header_returns_none_for_data():
    assert parse_header("hello | world") is None


# ── HEADER_RE is the shared symbol vocab.py now imports ──────────────────
def test_header_re_importable_from_vocab():
    """vocab.py aliases HEADER_RE as _HEADER_RE; confirm they're the same
    compiled pattern so there's only one source of truth."""
    from vocab import _HEADER_RE
    assert _HEADER_RE is HEADER_RE
