"""English<->French pairs: registry lookup per L2 (dialect aware), inventories,
English coda skip, uvular cue logic, coaching/priors layering."""

import numpy as np
import pytest
import soundfile as sf

from realised_phone import coaching, inventory
from realised_phone.detectors.rhotic import RhoticDetector
from realised_phone.learner import prior_for
from realised_phone.pipeline import Sources, analyse, source_for
from realised_phone.registry import Registry, RegistryEntry
from conftest import perro_alignment
from synth import SR, vrv


def test_registry_find_by_language_and_dialect():
    reg = Registry.load()
    notes = []
    assert source_for(reg, "aligner", "fr", notes) == "mfa-french_mfa"
    assert source_for(reg, "recognizer", "fr", notes) == "cnam-french"
    assert source_for(reg, "aligner", "en", notes) == "mfa-english_mfa"
    assert source_for(reg, "aligner", "es", notes) == "mfa-spanish_mfa"
    assert notes == []
    # dialect: exact code first, then base language with a note
    reg2 = Registry([RegistryEntry("nl-generic", "aligner", "1", "candidate", languages=["nl"]),
                     RegistryEntry("vl-specific", "aligner", "1", "candidate", languages=["nl-be"])])
    assert reg2.find("aligner", "nl-be") == (reg2.get("vl-specific"), False)
    assert reg2.find("aligner", "nl") == (reg2.get("nl-generic"), False)
    reg3 = Registry([RegistryEntry("nl-generic", "aligner", "1", "candidate", languages=["nl"])])
    n = []
    assert source_for(reg3, "aligner", "nl-be", n) == "nl-generic" and "not modelled separately" in n[0]


@pytest.mark.parametrize("pair,target,canon,error_cls", [
    (("en", "fr"), "ʁ", "uvular", "english_r"),
    (("fr", "en"), "ɹ", "english_r", "uvular"),
])
def test_pair_inventories(pair, target, canon, error_cls):
    inv = inventory.load(*pair)
    assert inv.generic is False
    t = inv.target(target)
    assert t.canonical.cls == canon and error_cls in set(t.phone_class.values())
    assert t.detector == "rhotic"


def test_every_source_language_has_french_and_english_targets():
    for l1 in ("de", "es", "it", "nl", "pt"):
        assert inventory.load(l1, "fr").target("ʁ").canonical.cls == "uvular"
        assert inventory.load(l1, "en").target("ɹ").canonical.cls == "english_r"
    assert inventory.load("fr", "en").target("ɹ").skip == ["coda"]


def _uv_measure(**kw):
    m = {"n_occlusions": 2, "intervals_ms": [30.0], "f3_ratio": 0.97, "f3_low_fraction": 0.0,
         "f3_reliable": True, "f2_ratio": 0.8, "voiced_fraction": 0.9, "duration_ms": 90.0}
    m.update(kw)
    return m


def test_uvular_cue_rule():
    d = RhoticDetector()
    t = inventory.load("en", "fr").target("ʁ")
    top = lambda m: t.phone_class[max(s := d.scores(m, t.phones, t.phone_class), key=s.get)] if d.scores(m, t.phones, t.phone_class) else "abstain"  # noqa: E731
    assert top(_uv_measure()) == "uvular"                        # backed F2, dips of a uvular trill
    assert top(_uv_measure(f2_ratio=1.1, voiced_fraction=0.3)) == "uvular"   # devoiced [χ]
    assert top(_uv_measure(f2_ratio=1.1, voiced_fraction=0.9)) == "trill"    # front, voiced -> not uvular
    assert top(_uv_measure(duration_ms=40.0, n_occlusions=1, intervals_ms=[])) == "tap"   # too short
    assert top(_uv_measure(f3_ratio=0.6, f3_low_fraction=1.0)) == "english_r"
    # uvular never asserted when it isn't a candidate (e.g. the en-es file has ʁ; a custom one might not)
    es_like = {"r": "trill", "ɾ": "tap"}
    assert "ʁ" not in d.scores(_uv_measure(), ["r", "ɾ"], es_like)


def test_english_coda_r_is_not_judged(tmp_path):
    x, seg = vrv("english_r")
    wav = tmp_path / "car.wav"
    sf.write(wav, x / np.abs(x).max() * 0.9, SR)
    al = perro_alignment(seg, len(x) / SR, target="ɹ", word="car")
    al.phones = al.phones[:2]                          # r is now word-final -> coda
    reg = Registry([e for e in Registry.load().entries() if e.kind != "recognizer"])
    a = analyse(str(wav), "car", "fr", "en", transcript="car", registry=reg,
                allow_candidates=True, sources=Sources(aligner=lambda _w, _t: al))
    assert a.verdicts == []


def test_french_l2_english_r_detected(tmp_path):
    x, seg = vrv("english_r")
    wav = tmp_path / "rouge.wav"
    sf.write(wav, x / np.abs(x).max() * 0.9, SR)
    reg = Registry([e for e in Registry.load().entries() if e.kind != "recognizer"])
    a = analyse(str(wav), "rouge", "en", "fr", transcript="rouge", registry=reg, allow_candidates=True,
                sources=Sources(aligner=lambda _w, _t: perro_alignment(seg, len(x) / SR, target="ʁ", word="rouge")))
    (v,) = a.verdicts
    assert v.target == "ʁ" and v.realised_class == "english_r" and v.correct is False


def test_fr_en_coaching_and_priors():
    assert coaching.step("en", "fr", "ʁ", "english_r", 3, allow_draft=True)["minimal_pairs"]
    assert "tip" in coaching.step("fr", "en", "ɹ", "uvular", 2, allow_draft=True)["text"]
    a, b, e = prior_for("en", "fr", "y", "intervocalic")
    assert (a, b) == (1.0, 4.0) and "flege1987" in e["refs"]
    assert prior_for("fr", "en", "θ", "word_initial")[2]["expected_errors"] == ["sibilant", "stop"]
