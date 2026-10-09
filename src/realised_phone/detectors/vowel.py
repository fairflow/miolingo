"""
Vowel-quality detector (HANDOFF §1b source 3: "vowel quality F1/F2, F3 for rounding,
e.g. French /y/"). Speaker-normalised formants at the vowel's middle half:
F1, F2, F3 divided by the speaker's median over voiced frames of the same utterance.

Each modelled vowel (data/calibration/vowel.yaml) is a diagonal Gaussian in that space,
fitted on dev tokens by scripts/realised_phone/calibrate_vowel.py.

It votes on BACKNESS only (calibration `vote`): on Common Phone test the four-way
y/i/u/goose posterior named native French [y] correctly only 36% of the time, but F2
alone separates front [y] from back [u] (results doc, 2026-10-01). Each group's
representative model (y for front, u for back) is scored on the vote features; the group's
mass goes to the first group member among the target's candidates, and
`compatible_classes` tells the combiner which classes a "front" or "back" vote cannot
tell apart (front: y and i), so a recognizer [i] is not a disagreement.
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

    def posteriors(self, m: dict, phones: list[str], features=FEATURES) -> dict[str, float]:
        models = self.cal.get("models") or {}
        if any(m.get(f) is None for f in features):
            return {}
        idx = [FEATURES.index(f) for f in features]
        z = np.array([m[f] for f in features])
        ll = {}
        for p in phones:
            mod = models.get(norm_ipa(p))
            if mod is None:
                continue
            mu, sd = np.array(mod["mean"])[idx], np.array(mod["sd"])[idx]
            ll[p] = float(-0.5 * np.sum(((z - mu) / sd) ** 2) - np.sum(np.log(sd)))
        if len(ll) < 2:
            return {}                      # nothing to discriminate
        mx = max(ll.values())
        e = {p: np.exp(v - mx) for p, v in ll.items()}
        tot = sum(e.values())
        return {p: v / tot for p, v in e.items()}

    def _groups(self, candidates: list[str]) -> dict[str, tuple[str, str]]:
        """group -> (representative model, candidate that receives the group's mass)."""
        vote = self.cal.get("vote") or {}
        out = {}
        cands = [norm_ipa(c) for c in candidates]
        for g, members in (vote.get("groups") or {}).items():
            members = [norm_ipa(p) for p in members]
            rep = next((p for p in members if p in (self.cal.get("models") or {})), None)
            dest = next((p for p in members if p in cands), None)
            if rep and dest:
                out[g] = (rep, dest)
        return out

    def scores(self, m: dict, candidates: list[str], phone_class: dict[str, str]) -> dict[str, float]:
        vote = self.cal.get("vote")
        if not vote:
            return self.posteriors(m, candidates)
        groups = self._groups(candidates)
        if len(groups) < 2:
            return {}
        sub = VowelDetector({**self.cal, "vote": None, "features": vote["features"]})
        post = sub.posteriors(m, [rep for rep, _ in groups.values()], vote["features"])
        return {dest: post[rep] for rep, dest in groups.values() if rep in post}

    def compatible_classes(self, top_class: str, candidates: list[str],
                           phone_class: dict[str, str]) -> list[str]:
        """Classes of every candidate in the same backness group as top_class."""
        vote = self.cal.get("vote") or {}
        for members in (vote.get("groups") or {}).values():
            classes = {phone_class[norm_ipa(p)] for p in members if norm_ipa(p) in phone_class}
            if top_class in classes:
                return sorted(classes)
        return [top_class]
