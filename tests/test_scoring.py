"""
Tests for scoring/comparison functions extracted from app.py.

These are pure functions with no Streamlit or database dependencies,
making them safe to test in isolation.
"""

import sys
from pathlib import Path

# Import the functions directly from app.py
# Once the refactor extracts these into scoring/, update the imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# We can't import app.py directly (it has Streamlit side effects at import time),
# so we extract the functions by reading the source. Post-refactor, these become
# clean imports like: from scoring.comparison import levenshtein_distance
#
# For now, we duplicate the pure logic here as a baseline. When the refactor
# extracts these functions, we swap to real imports and these tests become
# regression guards.


def levenshtein_distance(s1: str, s2: str) -> int:
    """Copied from app.py:1803 — will be replaced by import after refactor."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalize_for_phoneme_scoring(s: str) -> str:
    """Copied from app.py:1318 — will be replaced by import after refactor."""
    import re
    if not s:
        return ""
    s = re.sub(r"\s+", "", s.strip())
    s = re.sub(r'_[:!|]+', '', s)
    return s


def compare_phonemes_edit_distance(user_phonemes: str, correct_phonemes: str):
    """Copied from app.py:1896 — will be replaced by import after refactor."""
    exact_match = user_phonemes == correct_phonemes
    if len(correct_phonemes) == 0:
        return exact_match, 0.0, len(user_phonemes)
    distance = levenshtein_distance(user_phonemes, correct_phonemes)
    max_length = max(len(user_phonemes), len(correct_phonemes))
    similarity = 1.0 - (distance / max_length)
    return exact_match, similarity, distance


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
        # Classic textbook example
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_unicode_phonemes(self):
        # IPA characters that the app actually compares
        assert levenshtein_distance("bɾazil", "bɾazil") == 0
        assert levenshtein_distance("bɾazil", "bɹazil") == 1  # ɾ vs ɹ


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
