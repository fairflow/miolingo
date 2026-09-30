"""
Pair-specific candidate inventory (HANDOFF §1a): for each target phone of L2,
the canonical phone plus known L1-transfer substitutes and dialect variants,
grouped into feedback classes. Data: data/pairs/<l1>-<l2>.yaml.
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

    def target(self, phone: str) -> Optional[Target]:
        return self.targets.get(norm_ipa(phone))


@lru_cache(maxsize=None)
def load(l1: str, l2: str) -> PairInventory:
    path = DATA_DIR / "pairs" / f"{l1}-{l2}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No candidate inventory for pair {l1}->{l2}: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    targets = {}
    for key, t in raw["targets"].items():
        cands = [Candidate(norm_ipa(c["phone"]), c["class"], c["kind"], c.get("note", ""))
                 for c in t["candidates"]]
        if sum(c.kind == "canonical" for c in cands) != 1:
            raise ValueError(f"{path}: target {key} needs exactly one canonical candidate")
        targets[norm_ipa(key)] = Target(norm_ipa(key), t.get("name", ""), t.get("detector"),
                                        cands, t.get("accept") or {})
    return PairInventory(raw["pair"]["l1"], raw["pair"]["l2"], raw.get("status", "draft"), targets)
