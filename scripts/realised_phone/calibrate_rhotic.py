#!/usr/bin/env python3
"""
Calibrate the rhotic detector thresholds on labelled real tokens (HANDOFF §1b:
"thresholds are calibrated on data, not hard-coded").

Token sources (labels from the aligner's canonical phones -- natives are assumed
to produce their dictionary form, English speakers their own [ɹ]):
  --cp-root/--lang es   native Spanish: aligned [r] -> trill, [ɾ] -> tap
                        (coda tokens excluded: the contrast is neutralised there)
  --english-tsv         wav<TAB>text English speech: aligned [ɹ] -> english_r

Each token is measured ONCE with permissive settings (all dips kept with their
depth/width), then thresholds are grid-searched offline. Objective: balanced
accuracy on decided tokens, subject to coverage >= --min-coverage. Prints a
confusion table and writes a suggested calibration YAML (with provenance) to --out.
A human reviews and commits it; the registry entry stays `candidate` until approved.

    MIO_MFA_CMD="conda run -n mfa mfa" venv/bin/python scripts/realised_phone/calibrate_rhotic.py \\
        --cp-root ~/datasets/common_phone/CP --lang es --n 300 \\
        --english-tsv ~/datasets/english_r.tsv --out /tmp/rhotic.suggested.yaml
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import itertools
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from realised_phone import corpora  # noqa: E402
from realised_phone.tokens import EN_LABELS, ES_LABELS, rhotic_tokens  # noqa: E402
from realised_phone.detectors.rhotic import RhoticDetector, load_calibration  # noqa: E402

CLASSES = ("trill", "tap", "english_r")


def permissive(cal: dict) -> dict:
    c = copy.deepcopy(cal)
    c["occlusion"]["min_depth_db"] = 2.0
    c["occlusion"]["max_width_ms"] = 80.0
    return c


def collect(stream, det):
    out = []
    for t in stream:
        p = t["phone"]
        m = det.measure(t["x"], t["sr"], (p.start, p.end))
        out.append({"label": t["label"], "context": t["context"], "m": m, "wav": t["wav"]})
    return out


def classify(m: dict, th: dict) -> str:
    occ = [o for o in m["occlusions"] if o["depth_db"] >= th["min_depth_db"] and o["width_ms"] <= th["max_width_ms"]]
    ts = [o["t"] for o in occ]
    ivs = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
    lowered = (m["f3_reliable"] and m["f3_ratio"] is not None and m["f3_ratio"] <= th["f3_ratio_max"]
               and (m["f3_low_fraction"] or 0) >= th["min_low_fraction"])
    if lowered:
        return "english_r"
    if len(occ) >= 2 and all(th["iv_lo"] <= v <= th["iv_hi"] for v in ivs):
        return "trill"
    if len(occ) >= 2:
        return "abstain"
    if len(occ) == 1:
        return "tap"
    return "abstain"


def evaluate(tokens, th):
    conf = defaultdict(Counter)
    for t in tokens:
        conf[t["label"]][classify(t["m"], th)] += 1
    recalls, decided, total = [], 0, 0
    for c in CLASSES:
        row = conf.get(c)
        if not row:
            continue
        n = sum(row.values())
        d = n - row["abstain"]
        total += n
        decided += d
        recalls.append(row[c] / d if d else 0.0)
    bal = float(np.mean(recalls)) if recalls else 0.0
    return bal, (decided / total if total else 0.0), conf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cp-root")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--split", default="dev", help="Common Phone split to calibrate on "
                    "(default dev; keep test for eval_rhotics.py)")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--native-tsv", help="wav<TAB>text native Spanish (alternative to --cp-root)")
    ap.add_argument("--english-tsv")
    ap.add_argument("--en-cp", action="store_true", help="English [ɹ] tokens from Common Phone en")
    ap.add_argument("--en-n", type=int, default=150)
    ap.add_argument("--cache", default=None, help="alignment cache dir (reused across runs)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--es-model", default="spanish_mfa")
    ap.add_argument("--es-dict", default="spanish_mfa")
    ap.add_argument("--en-model", default="english_mfa")
    ap.add_argument("--en-dict", default="english_us_mfa")
    ap.add_argument("--min-coverage", type=float, default=0.6)
    ap.add_argument("--out")
    args = ap.parse_args()

    base = load_calibration()
    det = RhoticDetector(permissive(base))
    tokens = []
    kw = dict(cache_dir=args.cache, jobs=args.jobs)
    if args.cp_root or args.native_tsv:
        items = (corpora.common_phone(args.cp_root, args.lang, args.split, args.n) if args.cp_root
                 else corpora.tsv(args.native_tsv))
        tokens += collect(rhotic_tokens(items, args.es_model, args.es_dict, ES_LABELS, "native_es",
                                        exclude_contexts=("coda",), **kw), det)
    if args.en_cp and args.cp_root:
        tokens += collect(rhotic_tokens(corpora.common_phone(args.cp_root, "en", args.split, args.en_n),
                                        args.en_model, args.en_dict, EN_LABELS, "english",
                                        exclude_contexts=("coda",), **kw), det)
    if args.english_tsv:
        # codas excluded: non-rhotic accents drop coda [ɹ], so its label would be wrong
        tokens += collect(rhotic_tokens(corpora.tsv(args.english_tsv), args.en_model, args.en_dict,
                                        EN_LABELS, "english", exclude_contexts=("coda",), **kw), det)
    if not tokens:
        print("no tokens collected", file=sys.stderr)
        return 2
    print("tokens:", dict(Counter(t["label"] for t in tokens)))

    grid = {
        "min_depth_db": [3.0, 4.0, 5.0, 6.0, 8.0],
        "max_width_ms": [30.0, 40.0, 50.0],
        "f3_ratio_max": [0.7, 0.74, 0.78, 0.82, 0.86],
        "min_low_fraction": [0.3, 0.5, 0.7],
        "iv_lo": [20.0, 25.0],
        "iv_hi": [60.0, 75.0, 90.0],
    }
    best = None
    for vals in itertools.product(*grid.values()):
        th = dict(zip(grid.keys(), vals))
        bal, cov, conf = evaluate(tokens, th)
        if cov < args.min_coverage:
            continue
        key = (round(bal, 4), round(cov, 4))
        if best is None or key > best[0]:
            best = (key, th, conf)
    if best is None:
        print(f"no setting reaches coverage {args.min_coverage}", file=sys.stderr)
        return 1
    (bal, cov), th, conf = best
    print(f"best balanced accuracy {bal:.3f} at coverage {cov:.3f}: {th}")
    print("confusion (rows = label):")
    for c in CLASSES:
        if c in conf:
            print(f"  {c:10s}", dict(conf[c]))

    cal = copy.deepcopy(base)
    cal["calibrated"] = True
    cal["occlusion"]["min_depth_db"] = th["min_depth_db"]
    cal["occlusion"]["max_width_ms"] = th["max_width_ms"]
    cal["formant"]["f3_ratio_max"] = th["f3_ratio_max"]
    cal["formant"]["min_low_fraction"] = th["min_low_fraction"]
    cal["trill"]["interval_ms"] = [th["iv_lo"], th["iv_hi"]]
    cal["provenance"] = {
        "method": "scripts/realised_phone/calibrate_rhotic.py grid search, balanced accuracy "
                  f"on decided tokens, coverage >= {args.min_coverage}",
        "clips": {"native": args.cp_root or args.native_tsv, "split": args.split,
                  "english": ("Common Phone en " + args.split) if args.en_cp else args.english_tsv,
                  "counts": dict(Counter(t["label"] for t in tokens))},
        "result": {"balanced_accuracy": bal, "coverage": cov,
                   "confusion": {k: dict(v) for k, v in conf.items()}},
        "date": dt.date.today().isoformat(),
    }
    if args.out:
        Path(args.out).write_text(yaml.safe_dump(cal, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
