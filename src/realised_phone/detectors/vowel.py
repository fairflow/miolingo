"""
Vowel-quality detector (HANDOFF §1b source 3: "vowel quality F1/F2, F3 for rounding,
e.g. French /y/"). Speaker-normalised formants at the vowel's middle half:
F1, F2, F3 divided by the speaker's median over voiced frames of the same utterance.

Each modelled vowel (data/calibration/vowel.yaml) is a diagonal Gaussian in that space,
fitted on dev tokens by scripts/realised_phone/calibrate_vowel.py. Scores are posteriors
(equal priors) over the candidate phones that have a model; candidates without one get
nothing (the detector is blind to them, e.g. [ju]). Near-ties therefore never vote.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from realised_phone.inventory import DATA_DIR, norm_ipa

DETECTOR_ID = "vowel-detector"
FEATURES = ("f1r", "f2r", "f3r")


@lru_cache(maxsize=None)
def load_calibration(path: Optional[str] = None) -> dict:
    p = Path(path) if path else DATA_DIR / "calibration" / "vowel.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {"models": {}}


class VowelDetector:
    detector_id = DETECTOR_ID

    def __init__(self, calibration: Optional[dict] = None):
        self.cal = calibration or load_calibration()

    def measure(self, x: np.ndarray, sr: int, seg: tuple[float, float], after_stop: bool = False) -> dict:
        import parselmouth
        snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
        fm = snd.to_formant_burg(time_step=0.005, max_number_of_formants=5,
                                 maximum_formant=self.cal.get("max_formant_hz", 5500.0))
        ts = np.array(fm.ts())
        F = [np.array([fm.get_value_at_time(k, t) for t in ts], dtype=float) for k in (1, 2, 3)]
        pitch = snd.to_pitch(time_step=0.005)
        voiced = np.isfinite(np.array([pitch.get_value_at_time(t) for t in ts]))
        a = seg[0] + 0.25 * (seg[1] - seg[0])
        b = seg[1] - 0.25 * (seg[1] - seg[0])
        mid = (ts >= a) & (ts <= b)
        out = {"duration_ms": round((seg[1] - seg[0]) * 1000, 1)}
        for k, name in enumerate(("f1", "f2", "f3")):
            ok = np.isfinite(F[k]) & voiced
            ref = float(np.median(F[k][ok])) if ok.sum() >= 10 else None
            v = float(np.median(F[k][mid & np.isfinite(F[k])])) if (mid & np.isfinite(F[k])).sum() >= 2 else None
            out[name] = None if v is None else round(v, 1)
            out[name + "r"] = None if (v is None or not ref) else round(v / ref, 4)
        return out

    def posteriors(self, m: dict, phones: list[str]) -> dict[str, float]:
        models = self.cal.get("models") or {}
        if any(m.get(f) is None for f in FEATURES):
            return {}
        z = np.array([m[f] for f in FEATURES])
        ll = {}
        for p in phones:
            mod = models.get(norm_ipa(p))
            if mod is None:
                continue
            mu, sd = np.array(mod["mean"]), np.array(mod["sd"])
            ll[p] = float(-0.5 * np.sum(((z - mu) / sd) ** 2) - np.sum(np.log(sd)))
        if len(ll) < 2:
            return {}                      # nothing to discriminate
        mx = max(ll.values())
        e = {p: np.exp(v - mx) for p, v in ll.items()}
        tot = sum(e.values())
        return {p: v / tot for p, v in e.items()}

    def scores(self, m: dict, candidates: list[str], phone_class: dict[str, str]) -> dict[str, float]:
        return self.posteriors(m, candidates)
