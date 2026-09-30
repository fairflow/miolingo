"""
One attempt -> AttemptAnalysis (spec "Flow for one attempt").

  gate (Whisper transcript covers the target words)
  -> align (MFA on the KNOWN text)
  -> per aligned phone that the pair inventory lists as a target:
       detector evidence (source 3) + recognizer evidence (source 2)
       -> combine -> Verdict
The result is evidence for the existing scorer/UI/learner model; nothing here scores.

Every model/detector goes through the registry. Without allow_candidates=True
only `approved` entries run (none are, until Matthew approves), so in
production this returns a gated/empty analysis rather than unapproved claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from realised_phone import combine as comb
from realised_phone import gate as gate_mod
from realised_phone import inventory as inv
from realised_phone.align import AlignmentError, context_of, mfa_align, window
from realised_phone.detectors import DETECTORS
from realised_phone.detectors.rhotic import is_stop
from realised_phone.model import Alignment, AttemptAnalysis, GateResult, Verdict
from realised_phone.recognizer import RecognizerSource, candidate_scores
from realised_phone.registry import APPROVED, ModelNotApproved, Registry


def source_for(reg: Registry, kind: str, l2: str, notes: Optional[list] = None) -> Optional[str]:
    """Registry id of the first `kind` (aligner/recognizer) entry for L2 (dialect first)."""
    e, dialect_fallback = reg.find(kind, l2)
    if e is not None and dialect_fallback and notes is not None:
        notes.append(f"{kind} {e.id} is for {l2.split('-')[0]}; dialect {l2} not modelled separately")
    return e.id if e else None


@dataclass
class Sources:
    """Injectable evidence sources (tests pass fakes; defaults resolve from registry)."""
    aligner: Optional[Callable[[str, str], Alignment]] = None
    recognizer: Optional[RecognizerSource] = None
    detectors: dict = field(default_factory=dict)       # detector name -> instance


def _load_wav(path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf
    x, sr = sf.read(path, dtype="float64")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x, sr


def analyse(wav_path: str, target_text: str, l1: str, l2: str, *,
            transcript: Optional[str] = None,
            registry: Optional[Registry] = None,
            allow_candidates: bool = False,
            sources: Optional[Sources] = None,
            min_agreeing_sources: int = 2,
            skip_gate: bool = False,
            targets: Optional[list[str]] = None) -> AttemptAnalysis:
    """targets: inventory targets to analyse. Default: those with a contrast
    detector (the slice: rhotics) -- a recognizer alone can only ever give
    'tentative', so other targets are opt-in (pass e.g. list(pair.targets))."""
    reg = registry or Registry.load()
    pair = inv.load(l1, l2)
    used: dict[str, str] = {}
    notes: list[str] = []
    src = sources or Sources()

    def _use(model_id: str):
        """Registry check; None if refused (recorded in notes)."""
        try:
            e = reg.require(model_id, allow_candidates=allow_candidates)
        except ModelNotApproved as ex:
            if str(ex) not in notes:
                notes.append(str(ex))
            return None
        used[e.id] = e.status
        return e

    # 1. Gate
    if skip_gate:
        g = GateResult(True, transcript or "", 1.0, [], "gate skipped")
    else:
        ge = _use("whisper-gate")
        if ge is None:
            return _empty(target_text, l1, l2, GateResult(False, transcript or "", 0.0, [],
                          "gate model not approved"), used, notes)
        g = gate_mod.check(target_text, transcript, ge.params.get("min_word_recall", 0.6))
    if not g.passed:
        return _empty(target_text, l1, l2, g, used, notes)

    # 2. Align
    aid = source_for(reg, "aligner", l2, notes)
    ae = _use(aid) if aid else None
    if ae is None:
        notes.append(f"no usable aligner for {l2}")
        return _empty(target_text, l1, l2, g, used, notes)
    align_fn = src.aligner or (lambda w, t: mfa_align(
        w, t, ae.params["acoustic_model"], ae.params["dictionary"],
        source_id=ae.id, version=ae.version, status=ae.status))
    try:
        al = align_fn(wav_path, target_text)
    except AlignmentError as ex:
        notes.append(f"alignment failed: {ex}")
        return _empty(target_text, l1, l2, g, used, notes)
    if al.oov:
        notes.append(f"words not in aligner dictionary: {', '.join(al.oov)}")

    # 3. Sources for segments
    rid = source_for(reg, "recognizer", l2, notes)
    re_ = _use(rid) if rid else None
    # Recognizer per target: the L2 default, unless the pair file names one for the target
    # (e.g. Flemish /ɣ/ -> clementapa-dutch, which can name the voiced 'zachte g').
    recs: dict = {}          # registry id -> (entry, RecognizerSource) | None (refused / failed)

    def _rec_for(tgt):
        if src.recognizer is not None:                    # injected (tests): used for all targets
            return (re_, src.recognizer) if re_ is not None else None
        rid_t = tgt.recognizer or (re_.id if re_ is not None else None)
        if rid_t is None:
            return None
        if rid_t not in recs:
            e = re_ if (re_ is not None and rid_t == re_.id) else _use(rid_t)
            recs[rid_t] = (e, RecognizerSource(e.id, e.version)) if e is not None else None
        return recs[rid_t]

    x, sr = _load_wav(wav_path)
    total = len(x) / sr

    scope = set(inv.norm_ipa(t) for t in targets) if targets is not None else \
        {k for k, t in pair.targets.items() if t.detector}
    verdicts: list[Verdict] = []
    for i, ph in enumerate(al.phones):
        tgt = pair.target(ph.label)
        if tgt is None or tgt.phone not in scope:
            continue
        ctx = context_of(al, i)
        if ctx in tgt.skip:
            continue          # e.g. English coda r: not judged (see pair file)
        pc = tgt.phone_class
        evidence = []
        # source 3: detector
        if tgt.detector:
            de = _use(_detector_registry_id(tgt.detector))
            if de is not None:
                det = src.detectors.get(tgt.detector) or DETECTORS[tgt.detector]()
                prev = al.phones[i - 1] if i > 0 and ph.start - al.phones[i - 1].end < 0.03 else None
                m = det.measure(x, sr, (ph.start, ph.end),
                                after_stop=bool(prev) and is_stop(prev.label))
                sc = det.scores(m, tgt.phones, pc)
                evidence.append(comb.make_evidence(
                    "detector", de.id, de.version, de.status, sc, pc,
                    de.params.get("margin", 0.3), measurements=m, window=(ph.start, ph.end)))
        # source 2: recognizer on the aligned window
        rr = _rec_for(tgt)
        if rr is not None:
            e, rec = rr
            w = window(ph, e.params.get("pad_s", 0.03), total)
            try:
                sc, unsup = candidate_scores(rec.posteriors(wav_path), w, tgt.phones)
                raw_max = max(sc.values(), default=0.0)
                # Too little posterior mass in the window: normalising would inflate
                # noise into a "decision", so the recognizer abstains (scores kept for trace).
                floor = e.params.get("min_raw", 0.02)
                used[e.id] = e.status
                evidence.append(comb.make_evidence(
                    "recognizer", e.id, e.version, e.status,
                    sc if raw_max >= floor else {}, pc,
                    e.params.get("margin", 0.25), unsupported=unsup, window=w,
                    measurements={"raw_scores": {k: round(v, 4) for k, v in sc.items()},
                                  "raw_max": round(raw_max, 4), "min_raw": floor}))
            except Exception as ex:  # noqa: BLE001 - model optional; record, don't fail
                notes.append(f"recognizer {e.id} unavailable: {ex}")
                used.pop(e.id, None)
                recs[e.id] = None
        if not evidence:
            continue          # no usable source for this target: nothing to report
        v = comb.combine(evidence, pc, min_agreeing_sources)
        w_i = ph.word_index if ph.word_index is not None else -1
        verdicts.append(Verdict(
            target=tgt.phone, target_class=tgt.canonical.cls,
            word=al.words[w_i].label if w_i >= 0 else "", word_index=w_i, phone_index=i,
            start=ph.start, end=ph.end, context=ctx, evidence=evidence,
            accepted_classes=tgt.accepted_classes(ctx), mild=dict(tgt.mild), **v))

    return AttemptAnalysis(target_text, l1, l2, g, al, verdicts, used,
                           learner_visible=bool(used) and all(s == APPROVED for s in used.values()),
                           notes=notes)


def _detector_registry_id(name: str) -> str:
    return f"{name}-detector"


def _empty(text, l1, l2, g, used, notes) -> AttemptAnalysis:
    return AttemptAnalysis(text, l1, l2, g, None, [], used,
                           learner_visible=False, notes=notes)
