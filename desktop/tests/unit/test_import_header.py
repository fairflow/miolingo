"""Tests for the ported language-pair header parser."""

from __future__ import annotations

import pytest

from miolingo_desktop.core.import_header import is_header_line, parse_header


@pytest.mark.parametrize(
    "line",
    ["(pt, en)", "# (pt, en)", "(  FR  ,  EN  )", "(de,nl)"],
)
def test_is_header_line_true(line: str) -> None:
    assert is_header_line(line) is True


@pytest.mark.parametrize(
    "line",
    ["bonjour | hello", "", "# a comment", "(toolongcode, en)", "(pt)"],
)
def test_is_header_line_false(line: str) -> None:
    assert is_header_line(line) is False


def test_parse_header() -> None:
    assert parse_header("(FR, EN)") == ("fr", "en")
    assert parse_header("not a header") is None
