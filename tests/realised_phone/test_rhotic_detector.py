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
    lo, hi = RhoticDetector().cal["trill"]["interval_ms"]
    assert all(lo <= iv <= hi for iv in m["intervals_ms"])
    assert m["calibrated"] is RhoticDetector().cal["calibrated"]   # carried into evidence


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


def test_stop_release_dip_ignored_after_a_stop():
    from realised_phone.detectors.rhotic import is_stop
    from synth import _dip_env
    assert is_stop("t") and is_stop("pʰ") and is_stop("d̪") and not is_stop("s") and not is_stop("a")
    x, seg = vrv("english_r")
    x = x * _dip_env(len(x), [seg[0] + 0.004], 0.014, 25.0)     # a release-like dip at the r onset
    d = RhoticDetector()
    assert d.measure(x, SR, seg)["n_occlusions"] == 1                    # counted as a contact...
    assert d.measure(x, SR, seg, after_stop=True)["n_occlusions"] == 0   # ...unless after a stop
    # a real tap contact 20 ms in is still counted after a stop
    xt, segt = vrv("tap")
    assert d.measure(xt, SR, segt, after_stop=True)["n_occlusions"] == 1
