"""Vowel-quality detector: Gaussian posteriors over modelled candidates; near-ties don't vote."""

import pytest

from realised_phone import inventory
from realised_phone.detectors.vowel import VowelDetector

CAL = {"models": {"y": {"mean": [1.0, 1.15, 0.99], "sd": [0.3, 0.1, 0.1]},
                  "u": {"mean": [1.0, 0.78, 1.0], "sd": [0.3, 0.1, 0.1]},
                  "i": {"mean": [1.0, 1.28, 1.13], "sd": [0.3, 0.1, 0.1]},
                  "ʉ": {"mean": [1.0, 1.03, 1.0], "sd": [0.3, 0.1, 0.1]}}}
T = inventory.load("en", "fr").target("y")


def m(f2r, f3r=1.0):
    return {"f1r": 1.0, "f2r": f2r, "f3r": f3r}


def test_clear_cases():
    d = VowelDetector(CAL)
    sc = d.scores(m(0.75), T.phones, T.phone_class)
    assert max(sc, key=sc.get) == "u" and sc["u"] > 0.9            # tu -> tout
    sc = d.scores(m(1.16, 0.98), T.phones, T.phone_class)
    assert max(sc, key=sc.get) == "y"
    sc = d.scores(m(1.30, 1.15), T.phones, T.phone_class)
    assert max(sc, key=sc.get) == "i"                               # unrounded: F3 higher


def test_unmodelled_candidates_get_nothing_and_missing_formants_abstain():
    d = VowelDetector(CAL)
    assert "ju" not in d.scores(m(1.0), T.phones, T.phone_class)
    assert d.scores({"f1r": None, "f2r": 1.0, "f3r": 1.0}, T.phones, T.phone_class) == {}
    assert VowelDetector({"models": {"y": CAL["models"]["y"]}}).scores(m(1.0), T.phones, T.phone_class) == {}


def test_goose_vs_y_is_a_near_tie_in_the_overlap():
    d = VowelDetector(CAL)
    sc = d.scores(m(1.09, 0.995), ["y", "ʉ"], {"y": "front_rounded", "ʉ": "goose"})
    assert abs(sc["y"] - sc["ʉ"]) < 0.5                              # overlap -> no strong vote


def test_shipped_calibration_has_the_french_models():
    cal = VowelDetector().cal
    assert {"y", "u", "i", "ʉ"} <= set(cal["models"]) and cal["calibrated"] is True
    assert cal["models"]["y"]["mean"][1] > cal["models"]["u"]["mean"][1]   # y front, u back


# --- shipped backness-only vote ------------------------------------------------------------

def test_shipped_vote_is_front_back_only():
    d = VowelDetector()
    sc = d.scores(m(1.3), T.phones, T.phone_class)            # front
    assert set(sc) == {"y", "u"} and sc["y"] > 0.85           # i and ʉ get nothing
    sc = d.scores(m(0.7), T.phones, T.phone_class)            # back: tu -> tout
    assert sc["u"] > 0.9
    assert d.compatible_classes("front_rounded", T.phones, T.phone_class) == \
        ["front_rounded", "front_unrounded", "goose"]
    tu = inventory.load("en", "fr").target("u")               # target u: front mass -> goose
    sc = d.scores(m(1.3), tu.phones, tu.phone_class)
    assert set(sc) == {"ʉ", "u"} and sc["ʉ"] > 0.85


def _ev(source, scores, pc, compatible=()):
    from realised_phone.combine import make_evidence
    e = make_evidence(source, source, "t", "candidate", scores, pc, 0.3)
    e.compatible = list(compatible)
    return e


def test_coarse_front_vote_does_not_contradict_a_recognizer_i():
    from realised_phone.combine import combine
    from realised_phone.model import CONFIDENT, TENTATIVE, UNCERTAIN
    pc = T.phone_class
    front = _ev("detector", {"y": 0.95, "u": 0.05}, pc, ["front_unrounded", "goose"])
    r = combine([front, _ev("recognizer", {"i": 0.9, "y": 0.1}, pc)], pc)
    assert r["status"] == TENTATIVE and r["realised_class"] == "front_unrounded"
    r = combine([front, _ev("recognizer", {"y": 0.9, "i": 0.1}, pc)], pc)
    assert r["status"] == CONFIDENT and r["realised_class"] == "front_rounded"
    r = combine([front, _ev("recognizer", {"u": 0.9, "y": 0.1}, pc)], pc)   # real disagreement
    assert r["status"] == UNCERTAIN
