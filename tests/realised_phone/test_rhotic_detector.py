"""Rhotic detector on source-filter synthetic signals (cue logic, not calibration)."""

import numpy as np
import pytest
from scipy.signal import butter, sosfiltfilt

from realised_phone.detectors.rhotic import RhoticDetector
from realised_phone.inventory import load
from synth import SR, vrv

T = load("en", "es").target("r")


def top_class(kind, f0=120.0, x_fn=None):
    x, seg = vrv(kind, f0=f0)
    if x_fn:
        x = x_fn(x)
    d = RhoticDetector()
    m = d.measure(x, SR, seg)
    sc = d.scores(m, T.phones, T.phone_class)
    return (T.phone_class[max(sc, key=sc.get)] if sc else "abstain"), m, sc


@pytest.mark.parametrize("f0", [100.0, 120.0, 210.0])
@pytest.mark.parametrize("kind,expected", [("trill", "trill"), ("tap", "tap"),
                                           ("english_r", "english_r"), ("none", "abstain")])
def test_classes_across_voices(kind, expected, f0):
    got, m, _ = top_class(kind, f0)
    assert got == expected, m


def test_trill_measurements_are_traceable():
    _, m, _ = top_class("trill")
    assert m["n_occlusions"] >= 2
    assert all(25 <= iv <= 75 for iv in m["intervals_ms"])
    assert m["calibrated"] is False


def test_english_r_splits_evenly_over_indistinguishable_class():
    _, _, sc = top_class("english_r")
    assert sc["ɹ"] == pytest.approx(sc["ɻ"])
    assert "ʁ" not in sc                   # uvular is never asserted by this detector


def test_narrowband_audio_does_not_assert_english_r():
    # telephone-band: F3 tracking unreliable -> abstain rather than claim English r
    sos = butter(8, 3800, btype="low", fs=SR, output="sos")
    got, m, _ = top_class("english_r", x_fn=lambda x: sosfiltfilt(sos, x))
    assert m["f3_reliable"] is False
    assert got == "abstain"


def test_silence_segment_does_not_crash():
    d = RhoticDetector()
    x = 1e-4 * np.random.default_rng(0).standard_normal(SR // 2)
    m = d.measure(x, SR, (0.2, 0.3))
    assert d.scores(m, T.phones, T.phone_class) in ({}, {"ɾ": 0.8, "r": 0.2})
