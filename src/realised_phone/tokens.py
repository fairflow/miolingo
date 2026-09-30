"""
Labelled rhotic tokens from aligned corpora -- shared by the calibration and
evaluation scripts (scripts/realised_phone/). Labels come from the aligner's
canonical phones: natives are assumed to produce their dictionary form
(Spanish [r] -> trill, [ɾ] -> tap), English speakers their own [ɹ] -> english_r.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, Optional

from realised_phone.align import context_of, mfa_align_batch

ES_LABELS = {"r": "trill", "ɾ": "tap"}
EN_LABELS = {"ɹ": "english_r"}
FR_LABELS = {"ʁ": "uvular"}      # MFA french_mfa label for French r


def rhotic_tokens(items: Iterable[dict], acoustic_model: str, dictionary: str,
                  label_of: dict[str, str], source: str, *,
                  cache_dir: Optional[str] = None, jobs: int = 4,
                  exclude_contexts: tuple[str, ...] = ()) -> Iterator[dict]:
    import soundfile as sf
    items = [dict(it, id=it.get("id") or Path(it["wav"]).stem) for it in items]
    aligned = mfa_align_batch(items, acoustic_model, dictionary, cache_dir=cache_dir, jobs=jobs)
    for it in items:
        al = aligned.get(it["id"])
        if al is None:
            continue
        x, sr = sf.read(it["wav"], dtype="float64")
        if x.ndim > 1:
            x = x.mean(axis=1)
        for i, p in enumerate(al.phones):
            lab = label_of.get(p.label)
            if lab is None:
                continue
            ctx = context_of(al, i)
            if ctx in exclude_contexts:
                continue
            prev = al.phones[i - 1] if i > 0 and p.start - al.phones[i - 1].end < 0.03 else None
            yield {"wav": it["wav"], "utt": it["id"], "speaker": it.get("speaker", ""),
                   "prev": prev.label if prev else "",
                   "x": x, "sr": sr, "phone": p, "label": lab, "context": ctx, "source": source,
                   "word": al.words[p.word_index].label if p.word_index is not None else ""}
