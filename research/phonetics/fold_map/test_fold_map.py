"""
Tests for the espeak-ng allophony fold-map (beads miolingo-ark).

Guards the contract the weighted scorer (miolingo-8f0) depends on, and the two
modelling invariants that matter pedagogically:
  - tolerance is NOT transitive (real minimal pairs stay distinct);
  - genuine phoneme substitutions are never tolerated.
"""
import sys
from pathlib import Path

import pytest

# Standalone research module: make this directory importable whether run via
# pytest from the repo root or directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fold_map  # noqa: E402


ALL_LANGS = ["pt", "pt-pt", "fr", "nl", "en"]


@pytest.mark.parametrize("lang", ALL_LANGS)
def test_each_language_loads(lang):
    assert fold_map.inventory(lang)              # non-empty inventory
    assert isinstance(fold_map.tolerated_pairs(lang), frozenset)


def test_language_aliases():
    assert fold_map.tolerated_pairs("pt-br") == fold_map.tolerated_pairs("pt")
    assert fold_map.tolerated_pairs("en-gb") == fold_map.tolerated_pairs("en")
    with pytest.raises(KeyError):
        fold_map.tolerated_pairs("xx")


def test_identity_always_tolerated():
    assert fold_map.is_tolerated("pt", "a", "a")


def test_tolerated_pairs_are_symmetric():
    # pt s# -> z before voiced: a tolerated accent realization
    assert fold_map.is_tolerated("pt", "z", "ʃ")
    assert fold_map.is_tolerated("pt", "ʃ", "z")


def test_pt_pt_unstressed_reduction_tolerated():
    # European Portuguese reduces unstressed a->ɐ, o->u, e->ɨ
    assert fold_map.is_tolerated("pt-pt", "a", "ɐ")
    assert fold_map.is_tolerated("pt-pt", "o", "u")
    assert fold_map.is_tolerated("pt-pt", "e", "ɨ")


def test_real_substitutions_flagged():
    # k/g and p/b are genuine errors, never tolerated in any language
    for lang in ALL_LANGS:
        assert not fold_map.is_tolerated(lang, "k", "g")
        assert not fold_map.is_tolerated(lang, "p", "b")


def test_tolerance_not_transitive():
    # pt-pt: e~ɨ and ɛ~ɨ are tolerated, but pé[pɛ] vs pês[pe] is a real
    # minimal pair -> e~ɛ must NOT be tolerated.
    assert fold_map.is_tolerated("pt-pt", "e", "ɨ")
    assert fold_map.is_tolerated("pt-pt", "ɛ", "ɨ")
    assert not fold_map.is_tolerated("pt-pt", "e", "ɛ")

    # en: many vowels reduce to schwa, but they must not collapse into each
    # other -- bit/bet etc. stay distinct.
    assert fold_map.is_tolerated("en", "ɪ", "ə")
    assert fold_map.is_tolerated("en", "ʌ", "ə")
    assert not fold_map.is_tolerated("en", "ɪ", "ʌ")


def test_pairs_reference_real_inventory():
    # every tolerated pair touches at least one phone the language emits
    for lang in ALL_LANGS:
        inv = set(fold_map.inventory(lang))
        for pair in fold_map.tolerated_pairs(lang):
            assert inv & pair, f"{lang}: pair {pair} disjoint from inventory"
