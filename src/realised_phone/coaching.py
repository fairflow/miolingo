"""
Corrective coaching ladder (HANDOFF §3). Content is DATA authored/reviewed by
Matthew (data/coaching/<l1>-<l2>.yaml); Claude drafts, nothing ships unreviewed:
draft content is refused unless allow_draft=True (debug/testing).

Rung numbers match learner.LearnerModel.coaching_rung: 1 contrast,
2 articulation, 3 perception, 4 drills, 5 stabilisation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import yaml

from realised_phone.inventory import DATA_DIR, norm_ipa

RUNGS = ["contrast", "articulation", "perception", "drills", "stabilisation"]


class DraftContent(RuntimeError):
    pass


@lru_cache(maxsize=None)
def load(l1: str, l2: str) -> dict:
    """Pair-specific ladders, falling back to L1-agnostic any-<l2>.yaml for any
    (target, realised) pair the specific file doesn't cover."""
    out: dict = {"ladders": {}}
    for name in (f"any-{l2}", f"{l1}-{l2}"):            # specific overrides generic
        p = DATA_DIR / "coaching" / f"{name}.yaml"
        if p.exists():
            out["ladders"].update((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("ladders") or {})
    return out


def feature_contrast(target: str, realised: str) -> list[str]:
    """PanPhon features that differ, as '+feat -> -feat' strings (target -> realised).
    Empty when PanPhon can't tell them apart (e.g. trill vs tap)."""
    ft = _ft()
    a, b = ft.word_fts(target), ft.word_fts(realised)
    if not a or not b:
        return []
    va, vb = a[0], b[0]
    sym = {1: "+", -1: "-", 0: "0"}
    out = []
    for name in ft.names:
        x, y = va[name], vb[name]
        if x != y:
            out.append(f"{sym[x]}{name} -> {sym[y]}{name}")
    return out


@lru_cache(maxsize=1)
def _ft():
    import panphon
    return panphon.FeatureTable()


def ladder(l1: str, l2: str, target: str, realised_class: str,
           allow_draft: bool = False) -> Optional[dict]:
    data = load(l1, l2)
    entry = (data.get("ladders") or {}).get(f"{norm_ipa(target)}>{realised_class}")
    if entry is None:
        return None
    if entry.get("status") != "reviewed" and not allow_draft:
        raise DraftContent(f"coaching {target}>{realised_class} is {entry.get('status')}; "
                           "needs Matthew's review before learners see it")
    return entry


def step(l1: str, l2: str, target: str, realised_class: str, rung: int,
         realised_phone: Optional[str] = None, allow_draft: bool = False) -> Optional[dict]:
    """Content for rung 1..5 (clamped); None if no ladder for this pair."""
    entry = ladder(l1, l2, target, realised_class, allow_draft)
    if entry is None or rung <= 0:
        return None
    name = RUNGS[min(rung, len(RUNGS)) - 1]
    raw = entry.get(name) or {}
    content = {"steps": list(raw)} if isinstance(raw, list) else dict(raw)
    if name == "contrast" and realised_phone:
        content["auto"] = feature_contrast(target, realised_phone)
    return {"rung": rung, "name": name, "status": entry.get("status"), **content}
