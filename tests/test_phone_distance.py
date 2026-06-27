"""
App-integration tests for the weighted phone-distance scorer (beads miolingo-8f0).

Distinct from the research prototype's tests: this imports through the app's
module layout (src/ on path via conftest) to guard that the fold-map data and
loader were promoted into src/ipa/ and that scoring.phone_distance wires to them.
"""
import pytest

from ipa import fold_map
from scoring.phone_distance import score


def test_foldmap_data_shipped_in_app():
    assert set(fold_map.languages()) == {"pt", "pt-pt", "fr", "nl", "en"}
    assert "1.51.1" in fold_map.meta()["espeak_version"]


def test_exact_match_is_perfect():
    r = score("kazɐ", "kazɐ", "pt")
    assert r.exact_match and r.similarity == 1.0


def test_near_better_than_far():
    assert score("ɪ", "iː").similarity > score("a", "iː").similarity


def test_accent_tolerance_language_specific():
    # European Portuguese folds unstressed a->ɐ; Brazilian does not.
    assert score("kaza", "kazɐ", "pt-pt").similarity == 1.0
    assert score("kaza", "kazɐ", "pt").similarity < 1.0


def test_real_error_penalized():
    assert score("gazɐ", "kazɐ", "pt").similarity < 1.0


def test_unknown_language_does_not_crash():
    # falls back to pure feature distance, no fold-map
    r = score("kaza", "kazɐ", "xx-unknown")
    assert 0.0 <= r.similarity <= 1.0
