"""
Tests for scoring/comparison and phoneme functions.

Now imports from the extracted modules directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scoring.comparison import (
    levenshtein_distance,
    compare_phonemes_edit_distance,
)
from scoring.phonemes import normalize_for_phoneme_scoring


# ---------------------------------------------------------------------------
# Levenshtein distance
# ---------------------------------------------------------------------------

class TestLevenshteinDistance:
    def test_identical_strings(self):
        assert levenshtein_distance("abc", "abc") == 0

    def test_empty_strings(self):
        assert levenshtein_distance("", "") == 0

    def test_one_empty(self):
        assert levenshtein_distance("abc", "") == 3
        assert levenshtein_distance("", "abc") == 3

    def test_single_substitution(self):
        assert levenshtein_distance("abc", "abd") == 1

    def test_single_insertion(self):
        assert levenshtein_distance("abc", "abcd") == 1

    def test_single_deletion(self):
        assert levenshtein_distance("abcd", "abc") == 1

    def test_completely_different(self):
        assert levenshtein_distance("abc", "xyz") == 3

    def test_symmetry(self):
        assert levenshtein_distance("kitten", "sitting") == levenshtein_distance("sitting", "kitten")

    def test_known_value(self):
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_unicode_phonemes(self):
        assert levenshtein_distance("bɾazil", "bɾazil") == 0
        assert levenshtein_distance("bɾazil", "bɹazil") == 1


# ---------------------------------------------------------------------------
# Phoneme normalisation
# ---------------------------------------------------------------------------

class TestNormalizeForPhonemeScoring:
    def test_empty_string(self):
        assert normalize_for_phoneme_scoring("") == ""

    def test_none_returns_empty(self):
        assert normalize_for_phoneme_scoring(None) == ""

    def test_strips_whitespace(self):
        assert normalize_for_phoneme_scoring("a b c") == "abc"

    def test_strips_leading_trailing(self):
        assert normalize_for_phoneme_scoring("  abc  ") == "abc"

    def test_removes_espeak_pause_phonemes(self):
        assert normalize_for_phoneme_scoring("hello_:world") == "helloworld"
        assert normalize_for_phoneme_scoring("a_!b") == "ab"
        assert normalize_for_phoneme_scoring("a_|b") == "ab"
        assert normalize_for_phoneme_scoring("a_::b") == "ab"

    def test_combined_whitespace_and_pauses(self):
        assert normalize_for_phoneme_scoring(" a _: b _! c ") == "abc"


# ---------------------------------------------------------------------------
# Phoneme comparison (edit distance)
# ---------------------------------------------------------------------------

class TestComparePhonemes:
    def test_exact_match(self):
        match, sim, dist = compare_phonemes_edit_distance("abc", "abc")
        assert match is True
        assert sim == 1.0
        assert dist == 0

    def test_completely_different(self):
        match, sim, dist = compare_phonemes_edit_distance("abc", "xyz")
        assert match is False
        assert sim == 0.0
        assert dist == 3

    def test_empty_correct(self):
        match, sim, dist = compare_phonemes_edit_distance("abc", "")
        assert match is False
        assert sim == 0.0
        assert dist == 3

    def test_both_empty(self):
        match, sim, dist = compare_phonemes_edit_distance("", "")
        assert match is True
        assert sim == 0.0
        assert dist == 0

    def test_partial_match(self):
        match, sim, dist = compare_phonemes_edit_distance("abcd", "abce")
        assert match is False
        assert 0.0 < sim < 1.0
        assert dist == 1

    def test_similarity_range(self):
        _, sim, _ = compare_phonemes_edit_distance("hello", "hallo")
        assert 0.0 <= sim <= 1.0
