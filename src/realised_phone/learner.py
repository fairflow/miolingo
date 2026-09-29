"""
Adaptive learner model (HANDOFF §4).

Per (l2, target phone, context): a Beta(alpha, beta) over P(correct production),
seeded from research priors (data/priors/<l1>-<l2>.yaml), updated from verdicts
weighted by how sure the verdict is. Also: escalation state for the coaching
ladder (§3) and improvement feedback that never claims more than the evidence.

Pure Python + JSON (to_dict/from_dict). DB persistence is a follow-up (spec:
phone_verdicts table next to user_progress).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import yaml

from realised_phone.inventory import DATA_DIR, norm_ipa
from realised_phone.model import CONFIDENT, TENTATIVE, Verdict

UPDATE_WEIGHT = {CONFIDENT: 1.0, TENTATIVE: 0.25}   # uncertain / no_evidence: 0


@lru_cache(maxsize=None)
def load_priors(l1: str, l2: str) -> dict:
    p = DATA_DIR / "priors" / f"{l1}-{l2}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def prior_for(l1: str, l2: str, target: str, context: str) -> tuple[float, float, dict]:
    pr = load_priors(l1, l2)
    table = (pr.get("priors") or {}).get(norm_ipa(target)) or {}
    entry = table.get(context) or table.get("_default")
    if not entry:
        return 1.0, 1.0, {}                              # uninformative
    ab = pr["difficulty_to_prior"][entry["difficulty"]]
    return float(ab["alpha"]), float(ab["beta"]), entry


@dataclass
class PhoneState:
    alpha: float
    beta: float
    history: list[tuple[float, bool, str]] = field(default_factory=list)  # (ts, correct, status)

    @property
    def p_correct(self) -> float:
        return self.alpha / (self.alpha + self.beta)


@dataclass
class Escalation:
    rung: int = 0              # 0 = no coaching yet; 1..5 = ladder rungs
    fail_streak: int = 0
    ok_streak: int = 0


@dataclass
class LearnerModel:
    l1: str
    l2: str
    states: dict[str, PhoneState] = field(default_factory=dict)
    escalation: dict[str, Escalation] = field(default_factory=dict)
    base_n: int = 3            # escalate after N consecutive failures (tunable)
    deescalate_after: int = 2
    ladder_len: int = 5

    # --- state -------------------------------------------------------------
    @staticmethod
    def key(target: str, context: str) -> str:
        return f"{norm_ipa(target)}|{context}"

    def state(self, target: str, context: str) -> PhoneState:
        k = self.key(target, context)
        if k not in self.states:
            a, b, _ = prior_for(self.l1, self.l2, target, context)
            self.states[k] = PhoneState(a, b)
        return self.states[k]

    def update(self, v: Verdict, ts: Optional[float] = None) -> None:
        """Fold one verdict in. Only confident/tentative verdicts with a decided
        correctness move the estimate; uncertain ones are ignored (not failures)."""
        w = UPDATE_WEIGHT.get(v.status, 0.0)
        ok = v.correct
        if w == 0.0 or ok is None:
            return
        st = self.state(v.target, v.context)
        if ok:
            st.alpha += w
        else:
            st.beta += w
        st.history.append((ts if ts is not None else time.time(), bool(ok), v.status))
        if v.status == CONFIDENT:
            self._escalate(v, ok)

    # --- escalation (§3) -----------------------------------------------------
    def _esc_key(self, target: str, realised_class: str) -> str:
        return f"{norm_ipa(target)}>{realised_class}"

    def n_for(self, target: str, context: str) -> int:
        """Escalation threshold informed by the model: struggle -> escalate sooner."""
        return max(1, self.base_n - 1) if self.state(target, context).p_correct < 0.3 else self.base_n

    def _escalate(self, v: Verdict, ok: bool) -> None:
        if ok:
            # success de-escalates every open error pair for this target
            for k, e in self.escalation.items():
                if k.startswith(norm_ipa(v.target) + ">"):
                    e.ok_streak += 1
                    e.fail_streak = 0
                    if e.ok_streak >= self.deescalate_after and e.rung > 0:
                        e.rung -= 1
                        e.ok_streak = 0
            return
        e = self.escalation.setdefault(self._esc_key(v.target, v.realised_class), Escalation())
        e.fail_streak += 1
        e.ok_streak = 0
        if e.fail_streak >= self.n_for(v.target, v.context):
            e.rung = min(self.ladder_len, e.rung + 1)
            e.fail_streak = 0

    def coaching_rung(self, target: str, realised_class: str) -> int:
        e = self.escalation.get(self._esc_key(target, realised_class))
        return e.rung if e else 0

    # --- practice strategy -----------------------------------------------------
    def priorities(self, top: int = 5) -> list[tuple[str, float]]:
        """Weakest first (lowest P(correct)); ties broken by uncertainty."""
        def score(item):
            _k, s = item
            n = s.alpha + s.beta
            return (s.p_correct, -1.0 / n)
        return [(k, round(s.p_correct, 3)) for k, s in sorted(self.states.items(), key=score)][:top]

    # --- improvement feedback (never overclaims) -----------------------------
    def improvement(self, target: str, context: str, window: int = 10,
                    min_prob: float = 0.9, class_name: str = "") -> Optional[str]:
        st = self.state(target, context)
        conf = [ok for _ts, ok, status in st.history if status == CONFIDENT]
        if len(conf) < 2 * window:
            return None
        before, recent = conf[-2 * window:-window], conf[-window:]
        kb, kr = sum(before), sum(recent)
        if kr <= kb or prob_greater(kr, window - kr, kb, window - kb) < min_prob:
            return None
        what = class_name or f"[{norm_ipa(target)}]"
        return (f"{what} produced in {kr} of your last {window} attempts, "
                f"up from {kb} of {window} before")

    # --- persistence -------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"l1": self.l1, "l2": self.l2, "base_n": self.base_n,
                "states": {k: {"alpha": s.alpha, "beta": s.beta, "history": s.history}
                           for k, s in self.states.items()},
                "escalation": {k: vars(e) for k, e in self.escalation.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "LearnerModel":
        m = cls(d["l1"], d["l2"], base_n=d.get("base_n", 3))
        m.states = {k: PhoneState(v["alpha"], v["beta"], [tuple(h) for h in v["history"]])
                    for k, v in d.get("states", {}).items()}
        m.escalation = {k: Escalation(**v) for k, v in d.get("escalation", {}).items()}
        return m


def prob_greater(s1: int, f1: int, s2: int, f2: int, n: int = 20000, seed: int = 0) -> float:
    """P(p1 > p2) with p_i ~ Beta(1 + s_i, 1 + f_i). Monte Carlo, deterministic seed."""
    rng = random.Random(seed)
    wins = sum(rng.betavariate(1 + s1, 1 + f1) > rng.betavariate(1 + s2, 1 + f2) for _ in range(n))
    return wins / n
