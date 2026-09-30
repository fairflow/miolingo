"""
Pair-specific candidate inventory (HANDOFF §1a): for each target phone of L2,
the canonical phone plus known L1-transfer substitutes and dialect variants,
grouped into feedback classes. Data: data/pairs/<l1>-<l2>.yaml.

The learner's first language (L1) is the app's source language, and any
source != target pair is allowed. When no specific <l1>-<l2>.yaml exists,
the L1-agnostic data/pairs/any-<l2>.yaml is used (union of substitutes across
the app's source languages); `generic` is then True.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

DATA_DIR = Path(__file__).parent / "data"


def norm_ipa(s: str) -> str:
    """Canonical IPA form: NFC, ASCII g -> IPA ɡ, no stray whitespace."""
    return unicodedata.normalize("NFC", s.strip()).replace("g", "ɡ")


@dataclass
class Candidate:
    phone: str
    cls: str
    kind: str
    note: str = ""


@dataclass
class Target:
    phone: str
    name: str
    detector: Optional[str]
    candidates: list[Candidate]
    accept: dict[str, list[str]] = field(default_factory=dict)  # context -> correct classes

    def accepted_classes(self, context: str) -> list[str]:
        """Classes counted as correct in this context (default: canonical class only)."""
        return self.accept.get(context, [self.canonical.cls])

    @property
    def canonical(self) -> Candidate:
        return next(c for c in self.candidates if c.kind == "canonical")

    @property
    def phone_class(self) -> dict[str, str]:
        return {c.phone: c.cls for c in self.candidates}

    @property
    def phones(self) -> list[str]:
        return [c.phone for c in self.candidates]


@dataclass
class PairInventory:
    l1: str
    l2: str
    status: str
    targets: dict[str, Target] = field(default_factory=dict)
    generic: bool = False          # loaded from any-<l2>.yaml (no pair-specific file)

    def target(self, phone: str) -> Optional[Target]:
        return self.targets.get(norm_ipa(phone))


@lru_cache(maxsize=None)
def load(l1: str, l2: str) -> PairInventory:
    if l1 == l2:
        raise ValueError(f"source and target language are the same ({l1}): no L1->L2 pair")
    path = DATA_DIR / "pairs" / f"{l1}-{l2}.yaml"
    generic = not path.exists()
    if generic:
        path = DATA_DIR / "pairs" / f"any-{l2}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No candidate inventory for target language {l2} "
                                f"(neither {l1}-{l2}.yaml nor any-{l2}.yaml)")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    targets = {}
    for key, t in raw["targets"].items():
        cands = [Candidate(norm_ipa(c["phone"]), c["class"], c["kind"], c.get("note", ""))
                 for c in t["candidates"]]
        if sum(c.kind == "canonical" for c in cands) != 1:
            raise ValueError(f"{path}: target {key} needs exactly one canonical candidate")
        targets[norm_ipa(key)] = Target(norm_ipa(key), t.get("name", ""), t.get("detector"),
                                        cands, t.get("accept") or {})
    return PairInventory(l1, raw["pair"]["l2"], raw.get("status", "draft"), targets, generic)
