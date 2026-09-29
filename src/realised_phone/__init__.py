"""
Realised-phone identification (HANDOFF.md, beads miolingo-6vo).

For a learner utterance of a KNOWN target text, identify the phone actually
produced at each target position -- including phones foreign to the target
language (e.g. English [ɹ] for Spanish trilled /r/) -- with evidence, so the
existing scorer, the see/hear view, coaching and the learner model can use it.

This package produces evidence; it does NOT score (scoring stays in
src/scoring/). Every model it runs goes through registry.Registry, which refuses
anything Matthew has not approved unless the caller explicitly allows
candidates (debug/testing), in which case the analysis is marked not
learner-visible.

Spec: docs/dev-docs/REALISED_PHONE_SPEC.md
"""

from realised_phone.model import (  # noqa: F401
    AlignedInterval,
    Alignment,
    AttemptAnalysis,
    Evidence,
    GateResult,
    Verdict,
)
