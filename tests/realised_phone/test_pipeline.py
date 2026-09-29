"""End-to-end analyse() with a fake aligner/recognizer and the real detector on
synthetic audio. Includes the handoff's golden requirement: disagreement between
sources produces 'uncertain'."""

import numpy as np
import pytest
import soundfile as sf

from realised_phone.pipeline import Sources, analyse
from realised_phone.recognizer import Posteriors, RecognizerSource
from realised_phone.registry import Registry, RegistryEntry
from conftest import perro_alignment
from synth import SR, vrv

VOCAB = {"r": 0, "ɾ": 1, "ɹ": 2, "e": 3, "o": 4}


def fake_recognizer(favour: str):
    def post(_model, wav):
        n = int(sf.info(wav).duration / 0.02) + 1
        p = np.full((n, len(VOCAB)), 0.05)
        p[:, VOCAB[favour]] = 0.8
        return Posteriors(p / p.sum(1, keepdims=True), VOCAB)
    return RecognizerSource("fb-xlsr-53-espeak", "fake", posterior_fn=post)


def run(tmp_path, kind, favour=None, registry=None, allow=True, transcript="el perro"):
    x, seg = vrv(kind)
    wav = tmp_path / f"{kind}.wav"
    sf.write(wav, x / np.abs(x).max() * 0.9, SR)
    total = len(x) / SR
    src = Sources(aligner=lambda _w, _t: perro_alignment(seg, total),
                  recognizer=fake_recognizer(favour) if favour else None)
    if not favour:  # detector only: registry without the recognizer
        reg = Registry([e for e in Registry.load().entries() if e.kind != "recognizer"])
    else:
        reg = registry or Registry.load()
    return analyse(str(wav), "perro", "en", "es", transcript=transcript,
                   registry=reg, allow_candidates=allow, sources=src)


def only(a):
    assert len(a.verdicts) == 1, [v.describe() for v in a.verdicts]
    return a.verdicts[0]


def test_detector_and_recognizer_agree_confident(tmp_path):
    v = only(run(tmp_path, "trill", favour="r"))
    assert v.status == "confident" and v.realised_class == "trill" and v.correct is True
    assert {e.source for e in v.evidence} == {"detector", "recognizer"}


def test_tap_for_trill_is_an_error(tmp_path):
    v = only(run(tmp_path, "tap", favour="ɾ"))
    assert v.status == "confident" and v.realised_class == "tap" and v.correct is False


def test_english_r_confident_when_recognizer_names_it(tmp_path):
    v = only(run(tmp_path, "english_r", favour="ɹ"))
    assert v.status == "confident" and v.realised_class == "english_r"
    assert v.realised_phone == "ɹ"       # recognizer resolves ɹ vs ɻ


def test_disagreement_produces_uncertain(tmp_path):
    v = only(run(tmp_path, "trill", favour="ɾ"))
    assert v.status == "uncertain" and set(v.between) == {"trill", "tap"}
    assert v.correct is None
    assert "uncertain between" in v.describe()


def test_recognizer_blind_candidates_reported(tmp_path):
    v = only(run(tmp_path, "trill", favour="r"))
    rec = next(e for e in v.evidence if e.source == "recognizer")
    assert set(rec.unsupported) == {"ɻ", "ʁ"}      # not in the fake vocab


def test_detector_only_is_tentative(tmp_path):
    v = only(run(tmp_path, "trill"))
    assert v.status == "tentative" and v.realised_class == "trill"


def test_unapproved_models_refused_without_allow(tmp_path):
    a = run(tmp_path, "trill", favour="r", allow=False)
    assert a.verdicts == [] and a.learner_visible is False
    assert any("not approved" in n for n in a.notes)


def test_candidates_never_learner_visible(tmp_path):
    assert run(tmp_path, "trill", favour="r").learner_visible is False


def test_approved_sources_are_learner_visible(tmp_path):
    ok = dict(status="approved", approved_by="Matthew", approved_on="2026-10-01")
    reg = Registry([RegistryEntry(e.id, e.kind, e.version, languages=e.languages,
                                  params=e.params, **ok) for e in Registry.load().entries()])
    a = run(tmp_path, "trill", favour="r", registry=reg, allow=False)
    assert a.learner_visible is True and only(a).status == "confident"


def test_gate_failure_stops_analysis(tmp_path):
    a = run(tmp_path, "trill", favour="r", transcript="something else entirely")
    assert a.gate.passed is False and a.verdicts == [] and a.alignment is None


def test_analysis_serialises(tmp_path):
    import json
    d = run(tmp_path, "trill", favour="r").to_dict()
    assert json.loads(json.dumps(d, ensure_ascii=False))["verdicts"][0]["correct"] is True


@pytest.mark.parametrize("ctx_phones,expected", [(("e", "o"), "intervocalic")])
def test_context_recorded(tmp_path, ctx_phones, expected):
    assert only(run(tmp_path, "trill", favour="r")).context == expected
