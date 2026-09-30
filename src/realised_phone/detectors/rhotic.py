"""
Rhotic detector (HANDOFF §1b source 3): trill vs tap vs English approximant r.

  english_r  strongly lowered F3 over most of the segment (speaker-normalised
             against the utterance median; checked first, see scores())
  trill      ≥2 brief occlusions -- periodic dips in voiced-band intensity at a
             ~13-40 Hz contact rate
  tap        exactly one brief occlusion
  otherwise  abstain (e.g. no occlusion, no F3 lowering: approximant tap [ɾ̞],
             uvular, or a bad alignment) -- the detector does not guess.

  uvular     F3 NOT lowered, and (F2 lowered or mostly unvoiced), and long enough
             -- a conservative cue (CP dev: 44% of French [ʁ], 5% false on es
             tap/trill, 1% on English [ɹ]); only when uvular is a candidate.
[ɹ] vs [ɻ] are NOT separated here: english_r scores are split evenly over the class. Thresholds come from
data/calibration/rhotic.yaml.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from realised_phone.inventory import DATA_DIR

DETECTOR_ID = "rhotic-detector"


@lru_cache(maxsize=None)
def load_calibration(path: Optional[str] = None) -> dict:
    p = Path(path) if path else DATA_DIR / "calibration" / "rhotic.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _bandpass(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    from scipy.signal import butter, sosfiltfilt
    hi = min(hi, 0.45 * sr)
    sos = butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    return sosfiltfilt(sos, x)


def envelope_db(x: np.ndarray, sr: int, cal: dict) -> tuple[np.ndarray, np.ndarray]:
    """Amplitude envelope (dB) of the voiced band: |Hilbert| low-passed below the
    pitch range, so glottal-pulse ripple (>=80 Hz) is removed while the 13-40 Hz
    contact rate of a trill passes. Returns (times, env_db) at hop_ms resolution."""
    from scipy.signal import butter, hilbert, sosfiltfilt
    env = cal["envelope"]
    if len(x) < int(0.03 * sr):
        return np.zeros(0), np.zeros(0)
    y = _bandpass(x, sr, *env["bandpass_hz"])
    a = np.abs(hilbert(y))
    sos = butter(4, env["lowpass_hz"], btype="low", fs=sr, output="sos")
    a = np.maximum(sosfiltfilt(sos, a), 1e-9)
    hop = max(1, int(sr * env["hop_ms"] / 1000))
    idx = np.arange(0, len(a), hop)
    return idx / sr, 20 * np.log10(a[idx])


def find_occlusions(t: np.ndarray, env_db: np.ndarray, seg: tuple[float, float],
                    cal: dict) -> list[dict]:
    """Brief intensity dips inside the (tolerance-widened) segment."""
    from scipy.signal import find_peaks, peak_widths
    if len(env_db) < 5:
        return []
    occ = cal["occlusion"]
    hop_s = float(np.median(np.diff(t))) if len(t) > 1 else 0.001
    idx, props = find_peaks(-env_db, prominence=occ["min_depth_db"],
                            distance=max(1, int(occ["min_separation_ms"] / 1000 / hop_s)))
    if len(idx) == 0:
        return []
    widths = peak_widths(-env_db, idx, rel_height=0.5)[0] * hop_s * 1000
    tol = occ["edge_tolerance_ms"] / 1000
    out = []
    for k, i in enumerate(idx):
        if not (seg[0] - tol <= t[i] <= seg[1] + tol):
            continue
        if widths[k] > occ["max_width_ms"]:
            continue
        out.append({"t": round(float(t[i]), 4), "depth_db": round(float(props["prominences"][k]), 2),
                    "width_ms": round(float(widths[k]), 1)})
    return out


def formant_tracks(x: np.ndarray, sr: int, cal: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(times, F2, F3) via Praat Burg."""
    import parselmouth
    snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
    fm = snd.to_formant_burg(time_step=0.005, max_number_of_formants=5,
                             maximum_formant=cal["formant"]["max_formant_hz"])
    ts = np.array(fm.ts())
    f2 = np.array([fm.get_value_at_time(2, tt) for tt in ts], dtype=float)
    f3 = np.array([fm.get_value_at_time(3, tt) for tt in ts], dtype=float)
    return ts, f2, f3


def f3_track(x: np.ndarray, sr: int, cal: dict) -> tuple[np.ndarray, np.ndarray]:
    ts, _f2, f3 = formant_tracks(x, sr, cal)
    return ts, f3


def hf_energy_db(x: np.ndarray, sr: int, above_hz: float = 4100.0) -> float:
    """Energy above `above_hz` relative to total (dB). Telephone/8 kHz-sourced audio
    sits near -40 dB: F3 tracking is unreliable there, so English-r is not asserted."""
    if sr <= 2 * above_hz:
        return -120.0
    X = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float(10 * np.log10(X[f > above_hz].sum() / (X.sum() + 1e-20) + 1e-12))


def voiced_mask(x: np.ndarray, sr: int, ts: np.ndarray) -> np.ndarray:
    import parselmouth
    snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=0.005)
    f0 = np.array([pitch.get_value_at_time(tt) for tt in ts], dtype=float)
    return np.isfinite(f0) & (f0 > 0)


class RhoticDetector:
    """Evidence over rhotic candidates for one aligned segment."""

    detector_id = DETECTOR_ID

    def __init__(self, calibration: Optional[dict] = None):
        self.cal = calibration or load_calibration()

    def measure(self, x: np.ndarray, sr: int, seg: tuple[float, float]) -> dict:
        t, env = envelope_db(x, sr, self.cal)
        occl = find_occlusions(t, env, seg, self.cal)
        intervals = [round((b["t"] - a["t"]) * 1000, 1) for a, b in zip(occl, occl[1:])]
        ts, f2, f3 = formant_tracks(x, sr, self.cal)
        voiced = voiced_mask(x, sr, ts)
        seg_frames = (ts >= seg[0]) & (ts <= seg[1])
        v2 = np.isfinite(f2) & voiced
        f2_ratio = (float(np.nanmedian(f2[v2 & seg_frames]) / np.nanmedian(f2[v2]))
                    if (v2 & seg_frames).sum() >= 2 else None)
        voiced_frac = float(np.mean(voiced[seg_frames])) if seg_frames.sum() else None
        ok = np.isfinite(f3) & voiced
        ref = float(np.median(f3[ok])) if ok.sum() >= self.cal["formant"]["ref_min_frames"] else None
        in_seg = ok & (ts >= seg[0]) & (ts <= seg[1])
        seg_f3 = float(np.percentile(f3[in_seg], 20)) if in_seg.sum() >= 2 else None
        ratio = (seg_f3 / ref) if (seg_f3 and ref) else None
        fcal = self.cal["formant"]
        low_frac = (float(np.mean(f3[in_seg] / ref <= fcal["f3_ratio_max"]))
                    if (ref and in_seg.sum() >= 2) else None)
        hf = hf_energy_db(x, sr)
        return {"occlusions": occl, "n_occlusions": len(occl), "intervals_ms": intervals,
                "f3_segment_hz": None if seg_f3 is None else round(seg_f3, 1),
                "f3_reference_hz": None if ref is None else round(ref, 1),
                "f3_ratio": None if ratio is None else round(ratio, 3),
                "f3_low_fraction": None if low_frac is None else round(low_frac, 3),
                "hf_energy_db": round(hf, 1),
                "f3_reliable": hf >= fcal["min_hf_energy_db"],
                "f2_ratio": None if f2_ratio is None else round(f2_ratio, 3),
                "voiced_fraction": None if voiced_frac is None else round(voiced_frac, 3),
                "duration_ms": round((seg[1] - seg[0]) * 1000, 1),
                "calibrated": bool(self.cal.get("calibrated"))}

    def scores(self, m: dict, candidates: list[str], phone_class: dict[str, str]) -> dict[str, float]:
        """Map measurements to class scores, then spread over candidate phones.
        Returns {} (abstain) when the measurements don't support any class."""
        tr = self.cal["trill"]
        lo, hi = tr["interval_ms"]
        n = m["n_occlusions"]
        regular = all(lo <= iv <= hi for iv in m["intervals_ms"])
        fcal = self.cal["formant"]
        lowered = (m["f3_reliable"] and m["f3_ratio"] is not None
                   and m["f3_ratio"] <= fcal["f3_ratio_max"]
                   and (m["f3_low_fraction"] or 0.0) >= fcal["min_low_fraction"])
        cls: dict[str, float]
        uv = self.cal.get("uvular")
        uvular = (uv is not None and "uvular" in {phone_class.get(p) for p in candidates}
                  and m["f3_reliable"] and m["f3_ratio"] is not None
                  and m["f3_ratio"] > uv["f3_ratio_min"]
                  and ((m.get("f2_ratio") is not None and m["f2_ratio"] <= uv["f2_ratio_max"])
                       or (m.get("voiced_fraction") is not None and m["voiced_fraction"] < uv["voiced_max"]))
                  and m.get("duration_ms", 0) >= uv["min_duration_ms"])
        # F3 lowering first: on real English [ɹ] (LibriSpeech, MFA-aligned) the F3
        # cue is consistent while dip counting picks up neighbouring stop closures
        # (grave, principles). A tap/trill does not lower F3 like this.
        if lowered:
            cls = {"english_r": 0.85, "tap": 0.075, "trill": 0.075}
        elif uvular:
            # before contact counting: a uvular trill [ʀ] also shows periodic dips
            cls = {"uvular": 0.8, "tap": 0.1, "trill": 0.1}
        elif n >= tr["min_contacts"] and regular:
            cls = {"trill": 0.85, "tap": 0.15}
        elif n >= tr["min_contacts"]:            # several dips, irregular spacing
            cls = {"trill": 0.5, "tap": 0.5}
        elif n == 1:
            cls = {"tap": 0.8, "trill": 0.2}
        else:
            return {}
        out: dict[str, float] = {}
        for c, s in cls.items():
            members = [p for p in candidates if phone_class.get(p) == c]
            for p in members:
                out[p] = s / len(members)
        return out
