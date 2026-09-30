#!/usr/bin/env python3
"""
MFA alignment accuracy on rhotics against Common Phone's own time-aligned IPA
(labels/<utt>.json from extract_cp_parquet.py) -- evidence for the aligner's
registry entry (mfa-spanish_mfa).

Common Phone es marks tap as `r` and trill as `rː`; MFA spanish_mfa uses `ɾ` / `r`.
Rhotics are paired in order within each utterance (only utterances where both
alignments have the same number of rhotics). Reports boundary differences and
tap/trill label agreement. Both alignments are automatic, so this measures
agreement between two aligners, not accuracy against a human gold standard.

    venv/bin/python scripts/realised_phone/eval_alignment.py --tsv /opt/cpdata/es/test/list.tsv \\
        --cache /opt/align_cache --out research/phonetics/realised_phone/results/align_cp-es-test.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from realised_phone import corpora  # noqa: E402
from realised_phone.align import mfa_align_batch  # noqa: E402

CP_TO_CLASS = {"r": "tap", "rː": "trill"}
MFA_TO_CLASS = {"ɾ": "tap", "r": "trill"}


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 4) if xs else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tsv", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    items = list(corpora.tsv(args.tsv))
    aligned = mfa_align_batch(items, "spanish_mfa", "spanish_mfa", cache_dir=args.cache, jobs=args.jobs)
    lab_dir = Path(args.tsv).parent / "labels"
    d_start, d_end, d_mid, agree = [], [], [], Counter()
    skipped = Counter()
    for it in items:
        al = aligned.get(it["id"])
        lf = lab_dir / f"{it['id']}.json"
        if al is None or not lf.exists():
            skipped["no_alignment"] += 1
            continue
        cp = [(s, e, CP_TO_CLASS[sym]) for s, e, sym in json.loads(lf.read_text(encoding="utf-8"))
              if sym in CP_TO_CLASS]
        mf = [(p.start, p.end, MFA_TO_CLASS[p.label]) for p in al.phones if p.label in MFA_TO_CLASS]
        if len(cp) != len(mf):
            skipped["rhotic_count_mismatch"] += 1
            continue
        for (cs, ce, cc), (ms, me, mc) in zip(cp, mf):
            d_start.append(abs(ms - cs))
            d_end.append(abs(me - ce))
            d_mid.append(abs((ms + me) / 2 - (cs + ce) / 2))
            agree[(cc, mc)] += 1
    n = sum(agree.values())
    summary = {
        "label": Path(args.tsv).parent.name, "tsv": args.tsv, "date": dt.date.today().isoformat(),
        "aligner": "mfa spanish_mfa (acoustic 3.2.0) vs Common Phone MAU IPA",
        "n_utterances": len(items), "n_rhotics_paired": n, "skipped": dict(skipped),
        "boundary_abs_diff_s": {k: {"median": pct(v, 0.5), "p90": pct(v, 0.9), "mean": round(st.mean(v), 4) if v else None}
                                for k, v in (("start", d_start), ("end", d_end), ("midpoint", d_mid))},
        "midpoint_within_20ms": round(sum(x <= 0.02 for x in d_mid) / n, 3) if n else None,
        "class_agreement": {f"cp_{a}->mfa_{b}": c for (a, b), c in sorted(agree.items())},
        "class_agreement_rate": round(sum(c for (a, b), c in agree.items() if a == b) / n, 3) if n else None,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
