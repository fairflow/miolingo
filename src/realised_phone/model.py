"""
Records for realised-phone analysis. Plain dataclasses, JSON-serialisable via
to_dict(). Field meanings: docs/dev-docs/REALISED_PHONE_SPEC.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

# Verdict statuses, strongest first.
CONFIDENT = "confident"
TENTATIVE = "tentative"
UNCERTAIN = "uncertain"
NO_EVIDENCE = "no_evidence"


@dataclass
class AlignedInterval:
    start: float
    end: float
    label: str
    word_index: Optional[int] = None  # phones only: index into Alignment.words

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Alignment:
    words: list[AlignedInterval]
    phones: list[AlignedInterval]
    source_id: str = ""
    version: str = ""
    status: str = ""
    oov: list[str] = field(default_factory=list)

    def phones_of_word(self, word_index: int) -> list[AlignedInterval]:
        return [p for p in self.phones if p.word_index == word_index]


@dataclass
class GateResult:
    passed: bool
    transcript: str
    word_recall: float
    missing_words: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class Evidence:
    source: str                        # "alignment" | "recognizer" | "detector"
    source_id: str
    version: str
    status: str                        # registry status at time of use
    scores: dict[str, float]           # phone -> 0..1 over nameable candidates
    decisive: bool
    margin: float                      # class-level top - second
    top_class: Optional[str] = None
    # classes this source cannot tell apart from its top_class (a front/back-only vowel
    # vote says "front" for both [y] and [i]); empty = it separates every class
    compatible: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    measurements: dict = field(default_factory=dict)
    window: tuple[float, float] = (0.0, 0.0)


@dataclass
class Verdict:
    target: str
    target_class: str
    word: str
    word_index: int
    phone_index: int
    start: float
    end: float
    context: str
    status: str
    realised_class: Optional[str] = None
    realised_phone: Optional[str] = None
    between: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    accepted_classes: list[str] = field(default_factory=list)  # empty = [target_class]
    mild: dict[str, float] = field(default_factory=dict)       # class -> penalty (accent level)

    @property
    def correct(self) -> Optional[bool]:
        ok = self.accepted_classes or [self.target_class]
        if self.status == UNCERTAIN and self.between and set(self.between) <= set(ok):
            return True       # e.g. coda tap-vs-trill: either answer is correct
        if self.status not in (CONFIDENT, TENTATIVE) or self.realised_class is None:
            return None
        return self.realised_class in ok

    @property
    def penalty(self) -> Optional[float]:
        """For the scorer: 0 = correct, 1 = error, in between = accent-level variant (e.g. a
        Netherlands-style g in Flemish, 0.3). None when undecided (uncertain / no evidence)."""
        ok = self.correct
        if ok is None:
            return None
        if ok:
            return 0.0
        return self.mild.get(self.realised_class, 1.0)

    @property
    def severity(self) -> Optional[str]:
        p = self.penalty
        return None if p is None else ("correct" if p == 0 else "error" if p >= 1 else "accent")

    def describe(self) -> str:
        """One-line learner/debug wording. Never overstates: uncertain says so."""
        if self.status == NO_EVIDENCE:
            return f"/{self.target}/ in '{self.word}': no evidence"
        if self.status == UNCERTAIN:
            return (f"/{self.target}/ in '{self.word}': uncertain between "
                    + " and ".join(self.between))
        shown = self.realised_phone or self.realised_class
        ok = {"correct": "✓", "accent": "~", "error": "✗"}.get(self.severity or "", "?")
        return f"/{self.target}/ in '{self.word}': realised [{shown}] {ok} ({self.status})"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["correct"] = self.correct
        d["penalty"] = self.penalty
        d["severity"] = self.severity
        return d


@dataclass
class AttemptAnalysis:
    target_text: str
    l1: str
    l2: str
    gate: GateResult
    alignment: Optional[Alignment]
    verdicts: list[Verdict]
    sources: dict[str, str]            # source_id -> registry status used
    learner_visible: bool              # False if any source was not approved
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdicts"] = [v.to_dict() for v in self.verdicts]
        return d
