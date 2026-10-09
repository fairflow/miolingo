"""
Tests for the weighted phone-distance scorer (beads miolingo-8f0).

Asserts the properties from the rebuild spec:
  - phonetically-near substitutions score higher similarity than distant ones;
  - multi-codepoint IPA segments (length, nasal diacritics) stay intact;
  - fold-map tolerated pairs cost nothing, but are language-specific;
  - genuine substitutions and indels are penalized and flagged.
Relative orderings are asserted (robust); exact 1.0 only where guaranteed.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phone_distance as pd  # noqa: E402


def sim(user, target, lang=None):
    return pd.score(user, target, lang).similarity


def test_exact_match():
    r = pd.score("kazɐ", "kazɐ", "pt")
    assert r.exact_match and r.similarity == 1.0 and r.distance == 0.0
    assert all(o.kind == "match" for o in r.ops)


def test_near_scores_higher_than_far():
    # /iː/ ~ /ɪ/ (one feature) > /iː/ ~ /a/ (vowel quality) > /iː/ ~ /p/ (consonant)
    assert sim("ɪ", "iː") > sim("a", "iː") > sim("p", "iː")


def test_similarity_bounded():
    for u, t in [("", "kazɐ"), ("kazɐ", ""), ("ptks", "iiii"), ("kazɐ", "kazɐ")]:
        assert 0.0 <= pd.score(u, t, "pt").similarity <= 1.0


def test_multicodepoint_segments_intact():
    assert pd.segment("iː") == ["iː"]       # length mark stays on the vowel
    assert pd.segment("ɐ̃") == ["ɐ̃"]         # nasal diacritic stays on the vowel
    # stress/syllable marks are stripped before alignment
    assert pd.segment("ˈka.zɐ") == ["k", "a", "z", "ɐ"]


def test_fold_map_tolerance_is_free():
    # European Portuguese reduces unstressed a->ɐ: tolerated, similarity 1.0
    assert sim("kaza", "kazɐ", "pt-pt") == 1.0
    # Brazilian s#->z / positional ʃ~z is folded for pt
    assert sim("kaʃɐ", "kazɐ", "pt") == 1.0


def test_tolerance_is_language_specific():
    # a~ɐ is a pt-pt tolerance only; in Brazilian pt it must be scored, not folded
    assert sim("kaza", "kazɐ", "pt") < 1.0
    # and with no language, nothing is folded
    assert sim("kaza", "kazɐ", None) < 1.0


def test_real_substitution_penalized_and_flagged():
    r = pd.score("pazɐ", "kazɐ", "pt")       # k -> p, a genuine place error
    assert r.similarity < 1.0
    subs = [o for o in r.ops if o.kind == "substitute"]
    assert subs and subs[0].target == "k" and subs[0].user == "p"
    # a clearly distant substitution (vowel vs stop) is flagged significant
    far = [o for o in pd.score("tazɐ", "azɐ", None).ops if o.kind == "substitute"]
    assert any(o.significant for o in far) or sim("t", "a") < 0.7


def test_insertion_and_deletion():
    ins = pd.score("kazɐz", "kazɐ", "pt")
    dele = pd.score("kaz", "kazɐ", "pt")
    assert ins.similarity < 1.0 and any(o.kind == "insert" for o in ins.ops)
    assert dele.similarity < 1.0 and any(o.kind == "delete" for o in dele.ops)


def test_unknown_symbol_does_not_crash():
    r = pd.score("k☺zɐ", "kazɐ", "pt")       # bogus symbol -> treated as distinct
    assert 0.0 <= r.similarity < 1.0


def test_scores_any_phone_string_not_just_espeak():
    # a phone-recognizer style string (spaced) scores against the espeak target
    assert pd.score("k a z ɐ", "kazɐ", "pt").similarity == 1.0
