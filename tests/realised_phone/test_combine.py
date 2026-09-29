"""Combination rule (HANDOFF §1c): agree -> report; disagree -> uncertain, never a guess."""

from realised_phone.combine import combine, make_evidence
from realised_phone.inventory import load

PC = load("en", "es").target("r").phone_class


def ev(scores, margin=0.3, source="detector"):
    return make_evidence(source, source, "0", "candidate", scores, PC, margin)


def test_two_agreeing_sources_confident():
    v = combine([ev({"r": 0.9, "ɾ": 0.1}), ev({"r": 0.8, "ɾ": 0.2}, source="recognizer")], PC)
    assert v["status"] == "confident" and v["realised_class"] == "trill" and v["realised_phone"] == "r"
    assert 0.8 <= v["confidence"] <= 0.9


def test_single_decisive_source_is_only_tentative():
    v = combine([ev({"r": 0.9, "ɾ": 0.1})], PC)
    assert v["status"] == "tentative" and v["realised_class"] == "trill"


def test_disagreement_is_uncertain_between_both():
    v = combine([ev({"r": 0.9, "ɾ": 0.1}), ev({"ɾ": 0.85, "r": 0.15}, source="recognizer")], PC)
    assert v["status"] == "uncertain"
    assert set(v["between"]) == {"trill", "tap"}
    assert v["realised_class"] is None


def test_no_decisive_source_is_uncertain_not_a_guess():
    v = combine([ev({"r": 0.55, "ɾ": 0.45})], PC)
    assert v["status"] == "uncertain" and v["between"] == ["trill", "tap"]


def test_empty_or_abstaining_evidence_is_no_evidence():
    assert combine([], PC)["status"] == "no_evidence"
    assert combine([ev({})], PC)["status"] == "no_evidence"


def test_class_level_decision_with_unresolved_phone():
    # detector can't separate ɹ from ɻ: class decided, phone left open
    split = {"ɹ": 0.425, "ɻ": 0.425, "ɾ": 0.075, "r": 0.075}
    v = combine([ev(split), ev(split, source="recognizer")], PC)
    assert v["status"] == "confident" and v["realised_class"] == "english_r"
    assert v["realised_phone"] is None


def test_second_source_resolves_phone_within_class():
    split = {"ɹ": 0.425, "ɻ": 0.425, "ɾ": 0.075, "r": 0.075}
    v = combine([ev(split), ev({"ɹ": 0.8, "ɻ": 0.1, "r": 0.1}, source="recognizer")], PC)
    assert v["realised_phone"] == "ɹ"


def test_non_decisive_source_does_not_veto():
    v = combine([ev({"r": 0.9, "ɾ": 0.1}), ev({"ɾ": 0.52, "r": 0.48}, source="recognizer"),
                 ev({"r": 0.8, "ɾ": 0.2}, source="x")], PC)
    assert v["status"] == "confident" and v["realised_class"] == "trill"
