"""
Source-filter synthesis of vowel–rhotic–vowel test signals for the rhotic
detector. Not speech-realistic -- it isolates exactly the cues the detector
claims to use (occlusion dips; F3 lowering), so a pass means the logic works,
not that thresholds are calibrated (that needs real clips; see golden manifest).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

SR = 16000
VOWEL_A = (700.0, 1220.0, 2600.0, 3400.0)


def _resonator(f: float, bw: float, sr: int):
    r = np.exp(-np.pi * bw / sr)
    th = 2 * np.pi * f / sr
    a = [1.0, -2 * r * np.cos(th), r * r]
    b = [1.0 - r]
    return b, a


def synth(formant_track: np.ndarray, f0: float = 120.0, sr: int = SR,
          seed: int = 0) -> np.ndarray:
    """formant_track: (n_samples, 4) Hz. Block-wise time-varying cascade filter."""
    n = len(formant_track)
    src = np.zeros(n)
    period = int(sr / f0)
    src[::period] = 1.0
    src = lfilter([1.0], [1.0, -0.97], src)            # glottal tilt
    bws = (80.0, 100.0, 140.0, 200.0)
    out = src.copy()
    block = int(0.005 * sr)
    for k in range(4):
        y = np.zeros(n)
        zi = np.zeros(2)
        for s in range(0, n, block):
            f = float(formant_track[min(s + block // 2, n - 1), k])
            b, a = _resonator(f, bws[k], sr)
            y[s:s + block], zi = lfilter(b, a, out[s:s + block], zi=zi)
        out = y
    out /= np.max(np.abs(out)) + 1e-12
    rng = np.random.default_rng(seed)
    # Noise above the formant ceiling (6 kHz) so the signal looks wideband (real 16 kHz speech:
    # -9..-14 dB above 4.1 kHz); otherwise the detector's narrowband guard trips.
    from scipy.signal import butter, sosfilt
    hb = sosfilt(butter(6, 6000, btype="high", fs=sr, output="sos"), rng.standard_normal(n))
    hb *= 0.3 * np.std(out) / (np.std(hb) + 1e-12)
    return out + hb + 1e-3 * rng.standard_normal(n)


def _dip_env(n: int, centres_s: list[float], width_s: float, depth_db: float,
             sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    env_db = np.zeros(n)
    for c in centres_s:
        m = np.abs(t - c) < width_s / 2
        env_db[m] = np.minimum(env_db[m], -depth_db * 0.5 * (1 + np.cos(2 * np.pi * (t[m] - c) / width_s)))
    return 10 ** (env_db / 20)


def vrv(kind: str, sr: int = SR, f0: float = 120.0) -> tuple[np.ndarray, tuple[float, float]]:
    """Vowel [a] 250 ms + rhotic segment + [a] 250 ms. Returns (signal, segment)."""
    seg_len = {"trill": 0.110, "tap": 0.040, "english_r": 0.100, "none": 0.080}[kind]
    v = 0.25
    n = int((2 * v + seg_len) * sr)
    tr = np.tile(np.array(VOWEL_A), (n, 1))
    seg = (v, v + seg_len)
    if kind == "english_r":
        t = np.arange(n) / sr
        # F3 dips to 1600 Hz over the segment with 40 ms transitions
        w = np.clip(1 - np.maximum(np.abs(t - (seg[0] + seg[1]) / 2) - seg_len / 2, 0) / 0.04, 0, 1)
        tr[:, 2] = VOWEL_A[2] - w * (VOWEL_A[2] - 1600.0)
        tr[:, 1] = VOWEL_A[1] - w * 120.0
    x = synth(tr, f0=f0, sr=sr)
    if kind == "trill":
        x *= _dip_env(n, [seg[0] + 0.020, seg[0] + 0.055, seg[0] + 0.090], 0.016, 25.0, sr)
    elif kind == "tap":
        x *= _dip_env(n, [seg[0] + 0.020], 0.020, 25.0, sr)
    return x, seg
