"""
Dorsal (g/ch) detector for Dutch/Flemish [x ɣ] (HANDOFF §1b source 3, "fricative place").

  stop       deep closure (near-silence) inside the segment + a large closure-to-burst level
             swing -- what English speakers' [k]/[ɡ] substitutes look like
  fricative  no real silence + steady noise; then voicing splits voiceless [x χ] (Netherlands)
             from voiced [ɣ ʝ] (Flemish 'zachte g') -- voicing thresholds are uncalibrated
  otherwise  abstain. [h] vs [x] is never decided here (see calibration/dorsal.yaml).
Thresholds: data/calibration/dorsal.yaml.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from realised_phone.inventory import DATA_DIR

DETECTOR_ID = "dorsal-detector"


@lru_cache(maxsize=None)
def load_calibration(path: Optional[str] = None) -> dict:
    p = Path(path) if path else DATA_DIR / "calibration" / "dorsal.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _frame_db(x: np.ndarray, win: int) -> np.ndarray:
    if len(x) < win:
        return np.zeros(0)
    n = (len(x) - win) // max(1, win // 2) + 1
    return np.array([20 * np.log10(np.sqrt(np.mean(x[i * (win // 2): i * (win // 2) + win] ** 2)) + 1e-9)
                     for i in range(n)])


class DorsalDetector:
    detector_id = DETECTOR_ID

    def __init__(self, calibration: Optional[dict] = None):
        self.cal = calibration or load_calibration()

    def measure(self, x: np.ndarray, sr: int, seg: tuple[float, float], after_stop: bool = False) -> dict:
        win = max(1, int(sr * self.cal["frame_ms"] / 1000))
        s0, s1 = int(seg[0] * sr), int(seg[1] * sr)
        db = _frame_db(x[s0:s1], win)
        ref = float(np.percentile(_frame_db(x, win), 90)) if len(x) >= win else 0.0
        out = {"duration_ms": round((seg[1] - seg[0]) * 1000, 1), "after_stop": after_stop}
        if len(db) < 3:
            return {**out, "closure_db": None, "spread_db": None, "voiced_fraction": None}
        import parselmouth
        snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
        pitch = snd.to_pitch(time_step=0.005)
        ts = np.arange(seg[0], seg[1], 0.005)
        f0 = np.array([pitch.get_value_at_time(t) for t in ts])
        return {**out, "closure_db": round(float(db.min() - ref), 2),
                "spread_db": round(float(db.max() - db.min()), 2),
                "voiced_fraction": round(float(np.mean(np.isfinite(f0))), 3) if len(ts) else None,
                "calibrated": bool(self.cal.get("calibrated"))}

    def scores(self, m: dict, candidates: list[str], phone_class: dict[str, str]) -> dict[str, float]:
        if m.get("closure_db") is None:
            return {}
        st, fr, vo = self.cal["stop"], self.cal["fricative"], self.cal["voicing"]
        if m["closure_db"] <= st["closure_max_db"] and m["spread_db"] >= st["spread_min_db"]:
            cls = {"stop": 0.85, "fricative": 0.075, "voiced_fricative": 0.075}
        elif m["closure_db"] > fr["closure_min_db"] and m["spread_db"] < fr["spread_max_db"]:
            v = m.get("voiced_fraction")
            if v is not None and v >= vo["voiced_min"]:
                cls = {"voiced_fricative": 0.8, "fricative": 0.15, "stop": 0.05}
            elif v is not None and v <= vo["voiceless_max"]:
                cls = {"fricative": 0.8, "voiced_fricative": 0.15, "stop": 0.05}
            else:                              # a fricative, voicing unclear: no class decision
                cls = {"fricative": 0.475, "voiced_fricative": 0.475, "stop": 0.05}
        else:
            return {}
        out: dict[str, float] = {}
        for c, s in cls.items():
            members = [p for p in candidates if phone_class.get(p) == c]
            for p in members:
                out[p] = s / len(members)
        return out
