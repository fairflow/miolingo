"""Dutch (nl) and Flemish (nl-be) as distinct models; dorsal (g/ch) detector."""

import numpy as np
import pytest

from realised_phone import inventory
from realised_phone.detectors.dorsal import DorsalDetector
from realised_phone.pipeline import source_for
from realised_phone.registry import Registry

SR = 16000


def _vowel(n, rng):
    t = np.arange(n) / SR
    return 0.5 * np.sin(2 * np.pi * 120 * t) * (1 + 0.3 * np.sin(2 * np.pi * 700 * t)) + 0.005 * rng.standard_normal(n)


def _signal(kind, voiced=False, seed=0):
    """[a] 200 ms + target 90 ms + [a] 200 ms. fricative: steady noise; stop: silence + burst."""
    rng = np.random.default_rng(seed)
    v, s = int(0.2 * SR), int(0.09 * SR)
    mid = np.zeros(s)
    if kind == "fricative":
        mid = 0.12 * rng.standard_normal(s)
        if voiced:
            mid += 0.2 * np.sin(2 * np.pi * 120 * np.arange(s) / SR)
    elif kind == "stop":
        mid = 0.0005 * rng.standard_normal(s)                 # closure
        mid[int(0.07 * SR):int(0.08 * SR)] = 0.4 * rng.standard_normal(int(0.01 * SR))  # burst
    x = np.concatenate([_vowel(v, rng), mid, _vowel(v, rng)])
    return x, (0.2, 0.29)


@pytest.fixture
def target():
    return inventory.load("en", "nl").target("x")


def _top(kind, target, voiced=False):
    d = DorsalDetector()
    x, seg = _signal(kind, voiced)
    m = d.measure(x, SR, seg)
    sc = d.scores(m, target.phones, target.phone_class)
    if not sc:
        return "abstain", m
    cls = {}
    for p, s in sc.items():
        cls[target.phone_class[p]] = cls.get(target.phone_class[p], 0) + s
    top = max(cls, key=cls.get)
    return (top if cls[top] > 0.5 else "fricative-unsure"), m


def test_stop_vs_fricative(target):
    assert _top("stop", target)[0] == "stop"
    got, m = _top("fricative", target)
    assert got in ("fricative", "fricative-unsure"), m


def test_glottal_is_never_asserted(target):
    d = DorsalDetector()
    for kind in ("stop", "fricative"):
        x, seg = _signal(kind)
        sc = d.scores(d.measure(x, SR, seg), target.phones, target.phone_class)
        assert all(target.phone_class[p] != "glottal" or s == 0 for p, s in sc.items())


def test_dutch_and_flemish_are_distinct_models():
    nl, be = inventory.load("en", "nl"), inventory.load("en", "nl-be")
    assert nl.generic is False and be.generic is False
    # r: English-like approximant r is native in Netherlands codas only
    assert "english_r" in nl.target("r").accepted_classes("coda")
    assert "english_r" not in be.target("r").accepted_classes("coda")
    assert set(be.target("r").accepted_classes("word_initial")) == {"trill", "tap", "uvular"}
    # g: Netherlands accepts voiceless and voiced; Flanders only the voiced 'zachte g'
    assert set(nl.target("ɣ").accepted_classes("word_initial")) == {"fricative", "voiced_fricative"}
    assert be.target("ɣ").accepted_classes("word_initial") == ["voiced_fricative"]
    for t in (nl.target("x"), be.target("ɣ")):
        assert {"k", "ɡ", "h"} <= set(t.phones) and t.detector == "dorsal"


def test_same_language_dialects_are_not_a_pair():
    with pytest.raises(ValueError):
        inventory.load("nl", "nl-be")


def test_flemish_falls_back_to_dutch_aligner_with_a_note():
    reg, notes = Registry.load(), []
    assert source_for(reg, "aligner", "nl-be", notes) == "mfa-dutch_cv"
    assert "not modelled separately" in notes[0]
    assert source_for(reg, "aligner", "nl", []) == "mfa-dutch_cv"
    assert reg.get("clementapa-dutch").params["use"] == "testing-only"


def _flemish_g(realised_class, status="confident"):
    from realised_phone.model import Verdict
    t = inventory.load("en", "nl-be").target("ɣ")
    return Verdict(target="ɣ", target_class=t.canonical.cls, word="goed", word_index=0, phone_index=0,
                   start=0.1, end=0.2, context="word_initial", status=status,
                   realised_class=realised_class, accepted_classes=t.accepted_classes("word_initial"),
                   mild=dict(t.mild))


def test_netherlands_g_in_flemish_is_a_gentle_accent_not_an_error():
    acc = _flemish_g("fricative")                       # harsh Netherlands g
    assert acc.correct is False and acc.penalty == pytest.approx(0.3) and acc.severity == "accent"
    assert "~" in acc.describe()
    err = _flemish_g("stop")                            # English [ɡ]: a real error
    assert err.penalty == 1.0 and err.severity == "error"
    ok = _flemish_g("voiced_fricative")
    assert ok.penalty == 0.0 and ok.severity == "correct"
    assert _flemish_g(None, status="uncertain").penalty is None
    # Netherlands model: the same sound is simply correct
    assert inventory.load("en", "nl").target("ɣ").mild == {}


def test_learner_treats_accent_as_partial_slip_without_escalation():
    from realised_phone.learner import LearnerModel
    m = LearnerModel("en", "nl-be")
    st = m.state("ɣ", "word_initial")
    a0, b0 = st.alpha, st.beta
    for _ in range(5):
        m.update(_flemish_g("fricative"))
    assert st.alpha == pytest.approx(a0 + 5 * 0.7) and st.beta == pytest.approx(b0 + 5 * 0.3)
    assert m.coaching_rung("ɣ", "fricative") == 0       # accents never escalate the ladder
    for _ in range(3):
        m.update(_flemish_g("stop"))
    assert m.coaching_rung("ɣ", "stop") >= 1
