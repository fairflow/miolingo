"""
Combination rule (HANDOFF §1c, spec "Combination rule").

Sources agree -> report the realised phone; sources disagree -> "uncertain
between X and Y", never a guess. Decided at CLASS level first (phones a source
cannot tell apart share a class), then at phone level only if some decisive
source separates phones within the chosen class.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from realised_phone.model import (
    CONFIDENT, NO_EVIDENCE, TENTATIVE, UNCERTAIN, Evidence,
)


def class_scores(scores: dict[str, float], phone_class: dict[str, str]) -> dict[str, float]:
    """Sum phone scores into their classes (unknown phones are their own class)."""
    out: dict[str, float] = defaultdict(float)
    for ph, s in scores.items():
        out[phone_class.get(ph, ph)] += s
    return dict(out)


def top_two(d: dict[str, float]) -> tuple[Optional[str], float, Optional[str], float]:
    ranked = sorted(d.items(), key=lambda kv: kv[1], reverse=True)
    a = ranked[0] if ranked else (None, 0.0)
    b = ranked[1] if len(ranked) > 1 else (None, 0.0)
    return a[0], a[1], b[0], b[1]


def make_evidence(source: str, source_id: str, version: str, status: str,
                  scores: dict[str, float], phone_class: dict[str, str],
                  min_margin: float, **extra) -> Evidence:
    """Normalise scores, compute class-level margin and decisiveness."""
    total = sum(max(0.0, s) for s in scores.values())
    norm = {p: (max(0.0, s) / total if total > 0 else 0.0) for p, s in scores.items()}
    cs = class_scores(norm, phone_class)
    c1, s1, _c2, s2 = top_two(cs)
    margin = s1 - s2
    decisive = total > 0 and margin >= min_margin
    return Evidence(source=source, source_id=source_id, version=version, status=status,
                    scores=norm, decisive=decisive, margin=round(margin, 4),
                    top_class=c1 if total > 0 else None, **extra)


def detector_evidence(det, entry, scores: dict[str, float], candidates: list[str],
                      phone_class: dict[str, str], **extra) -> Evidence:
    """make_evidence for a detector, plus the classes its vote cannot separate."""
    ev = make_evidence("detector", entry.id, entry.version, entry.status, scores, phone_class,
                       entry.params.get("margin", 0.3), **extra)
    if ev.top_class and hasattr(det, "compatible_classes"):
        ev.compatible = [c for c in det.compatible_classes(ev.top_class, candidates, phone_class)
                         if c != ev.top_class]
    return ev


def combine(evidence: list[Evidence], phone_class: dict[str, str],
            min_agreeing_sources: int = 2) -> dict:
    """Return verdict fields: status, realised_class, realised_phone, between, confidence."""
    if not evidence or all(not e.scores for e in evidence):
        return dict(status=NO_EVIDENCE, realised_class=None, realised_phone=None,
                    between=[], confidence=0.0)

    votes = [e for e in evidence if e.decisive and e.top_class]
    voted = {e.top_class for e in votes}

    if len(voted) > 1:
        narrowed = _narrow(votes)
        if narrowed:
            # Only a coarse source disagrees, and only because it cannot separate the
            # classes: one source decided, so tentative at best.
            conf = sum(class_scores(e.scores, phone_class).get(narrowed, 0.0) for e in votes
                       if e.top_class == narrowed) / len(votes)
            fine = [e for e in votes if e.top_class == narrowed]
            return dict(status=TENTATIVE, realised_class=narrowed,
                        realised_phone=_phone_within(narrowed, fine, phone_class),
                        between=[], confidence=round(conf, 3))
        # Decisive sources disagree: say so, ranked by pooled support.
        pooled = _pooled(votes, phone_class)
        between = [c for c, _ in sorted(pooled.items(), key=lambda kv: -kv[1]) if c in voted]
        return dict(status=UNCERTAIN, realised_class=None, realised_phone=None,
                    between=between, confidence=0.0)

    if not votes:
        pooled = _pooled(evidence, phone_class)
        c1, _s1, c2, _s2 = top_two(pooled)
        return dict(status=UNCERTAIN, realised_class=None, realised_phone=None,
                    between=[c for c in (c1, c2) if c], confidence=0.0)

    cls = voted.pop()
    conf = sum(class_scores(e.scores, phone_class).get(cls, 0.0) for e in votes) / len(votes)
    status = CONFIDENT if len(votes) >= min_agreeing_sources else TENTATIVE
    return dict(status=status, realised_class=cls,
                realised_phone=_phone_within(cls, votes, phone_class),
                between=[], confidence=round(conf, 3))


def _narrow(votes: list[Evidence]) -> Optional[str]:
    """The single class every vote is compatible with, when the votes differ only
    because some sources are coarser (their `compatible` covers the others' class)."""
    def ok(e: Evidence) -> set:
        return set(e.compatible) | {e.top_class}
    common = set.intersection(*(ok(e) for e in votes))
    exact = {e.top_class for e in votes} & common
    return exact.pop() if len(exact) == 1 else None


def _pooled(evs: list[Evidence], phone_class: dict[str, str]) -> dict[str, float]:
    pooled: dict[str, float] = defaultdict(float)
    for e in evs:
        for c, s in class_scores(e.scores, phone_class).items():
            pooled[c] += s
    return dict(pooled)


def _phone_within(cls: str, votes: list[Evidence], phone_class: dict[str, str],
                  min_margin: float = 0.2) -> Optional[str]:
    """Name a single phone inside the class only if every voter that separates
    members agrees on it with a clear margin; else None (class-level only)."""
    members = [p for p, c in phone_class.items() if c == cls] or [cls]
    if len(members) == 1:
        return members[0]
    picks = set()
    for e in votes:
        sub = {p: e.scores.get(p, 0.0) for p in members if p in e.scores}
        p1, s1, _p2, s2 = top_two(sub)
        if p1 is not None and (s1 - s2) >= min_margin * max(s1, 1e-9):
            picks.add(p1)
    return picks.pop() if len(picks) == 1 else None
