"""
Model registry with the approval gate (HANDOFF §5, hard rule).

No recognition, alignment or detector model is used for learners until Matthew
has reviewed its test results and set status: approved in
data/model_registry.yaml. `require()` enforces this; tests and debug tooling may
pass allow_candidates=True, and the caller must then mark its output as not
learner-visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from realised_phone.inventory import DATA_DIR

CANDIDATE, APPROVED, RETIRED = "candidate", "approved", "retired"
_STATUSES = (CANDIDATE, APPROVED, RETIRED)


class ModelNotApproved(RuntimeError):
    pass


@dataclass
class RegistryEntry:
    id: str
    kind: str
    version: str
    status: str
    languages: list[str] = field(default_factory=list)
    results: list[str] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_on: Optional[str] = None
    params: dict = field(default_factory=dict)
    phones: list[str] = field(default_factory=list)


class Registry:
    def __init__(self, entries: list[RegistryEntry]):
        self._entries = {e.id: e for e in entries}

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Registry":
        path = path or (DATA_DIR / "model_registry.yaml")
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
        entries = []
        for r in raw:
            if r["status"] not in _STATUSES:
                raise ValueError(f"{path}: {r['id']} has unknown status {r['status']!r}")
            if r["status"] == APPROVED and not (r.get("approved_by") and r.get("approved_on")):
                raise ValueError(f"{path}: {r['id']} is approved without approved_by/approved_on")
            entries.append(RegistryEntry(
                id=r["id"], kind=r["kind"], version=str(r.get("version", "")),
                status=r["status"], languages=r.get("languages", []),
                results=r.get("results", []), approved_by=r.get("approved_by"),
                approved_on=r.get("approved_on"), params=r.get("params") or {},
                phones=r.get("phones", [])))
        return cls(entries)

    def get(self, model_id: str) -> RegistryEntry:
        try:
            return self._entries[model_id]
        except KeyError:
            raise ModelNotApproved(f"{model_id!r} is not in the model registry") from None

    def require(self, model_id: str, allow_candidates: bool = False) -> RegistryEntry:
        """Return the entry if usable; raise ModelNotApproved otherwise.
        Retired entries are never usable."""
        e = self.get(model_id)
        if e.status == APPROVED:
            return e
        if e.status == CANDIDATE and allow_candidates:
            return e
        raise ModelNotApproved(
            f"{model_id} is {e.status}; not approved for learners "
            f"(review its results and set status: approved in model_registry.yaml)")

    def entries(self) -> list[RegistryEntry]:
        return list(self._entries.values())
