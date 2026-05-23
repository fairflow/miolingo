"""Unit tests for the ported scoring/comparison logic."""

from __future__ import annotations

import pytest

from miolingo_desktop.core.comparison import (
    compare_phonemes,
    compare_phonemes_edit_distance,
    get_edit_operations,
    levenshtein_distance,
)


@pytest.mark.parametrize(
    ("s1", "s2", "expected"),
    [
        ("", "", 0),
        ("abc", "abc", 0),
        ("abc", "abd", 1),
        ("kitten", "sitting", 3),
        ("", "abc", 3),
        ("abc", "", 3),
        ("flaw", "lawn", 2),
    ],
)
def test_levenshtein_distance(s1: str, s2: str, expected: int) -> None:
    assert levenshtein_distance(s1, s2) == expected
    # Distance is symmetric.
    assert levenshtein_distance(s2, s1) == expected


def test_compare_phonemes_exact_match() -> None:
    exact, similarity, distance = compare_phonemes_edit_distance("bõʒuʁ", "bõʒuʁ")
    assert exact is True
    assert similarity == 1.0
    assert distance == 0


def test_compare_phonemes_partial() -> None:
    exact, similarity, distance = compare_phonemes_edit_distance("bõʒu", "bõʒuʁ")
    assert exact is False
    assert distance == 1
    assert similarity == pytest.approx(1.0 - 1 / 5)


def test_compare_phonemes_empty_reference() -> None:
    exact, similarity, distance = compare_phonemes_edit_distance("abc", "")
    assert exact is False
    assert similarity == 0.0
    assert distance == 3


def test_compare_phonemes_unknown_algorithm_falls_back() -> None:
    # Unknown algorithm must behave exactly like edit_distance (source parity).
    a = compare_phonemes("abc", "abd", algorithm="positional")
    b = compare_phonemes_edit_distance("abc", "abd")
    assert a == b


def test_get_edit_operations_roundtrip() -> None:
    ops = get_edit_operations("cat", "cut")
    kinds = [op[0] for op in ops]
    assert kinds == ["match", "substitute", "match"]
