#!/usr/bin/env python3
"""
Evaluate the rhotic evidence sources on labelled real tokens -- the test results
Matthew reviews before approving a source (HANDOFF §5 approval gate).

Per token: detector class, recognizer top class + margin, combined verdict.
Labels as in calibrate_rhotic.py: native Spanish aligned [r] -> trill, [ɾ] -> tap
(codas reported separately: tap/trill neutralised there); English speech aligned
[ɹ] -> english_r (stand-in for an English learner's r until learner recordings exist).

    MIO_MFA_CMD="conda run -n mfa mfa" venv/bin/python scripts/realised_phone/eval_rhotics.py \\
        --cp-root ~/datasets/common_phone/CP --n 300 --english-tsv ~/datasets/english_r.tsv \\
        --label cp-es-300 --out research/phonetics/realised_phone/results/rhotics_cp-es-300.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from realised_phone import combine as comb  # noqa: E402
from realised_phone import corpora, inventory  # noqa: E402
from realised_phone.align import AlignmentError, context_of, mfa_align, window  # noqa: E402
from realised_phone.detectors.rhotic import RhoticDetector, load_calibration  # noqa: E402
from realised_phone.recognizer import RecognizerSource, candidate_scores  # noqa: E402
from realised_phone.registry import Registry  # noqa: E402


def tokens(items, am, dic, label_of, source):
    import soundfile as sf
    for it in items:
        try:
            al = mfa_align(it["wav"], it["text"], am, dic)
        except AlignmentError as e:
            print(f"skip {it['wav']}: {e}", file=sys.stderr)
            continue
        x, sr = sf.read(it["wav"], dtype="float64")
        if x.ndim > 1:
            x = x.mean(axis=1)
        for i, p in enumerate(al.phones):
            if p.label in label_of:
                yield {"wav": it["wav"], "x": x, "sr": sr, "phone": p, "label": label_of[p.label],
                       "word": al.words[p.word_index].label if p.word_index is not None else "",
                       "context": context_of(al, i), "source": source}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cp-root")
    ap.add_argument("--native-tsv")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--split", default="test")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--english-tsv")
    ap.add_argument("--label", required=True, help="short name of this evaluation set")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-recognizer", action="store_true")
    args = ap.parse_args()

    reg = Registry.load()
    re_ = reg.get("fb-xlsr-53-espeak")
    de = reg.get("rhotic-detector")
    rec = None if args.no_recognizer else RecognizerSource(re_.id, re_.version)
    det = RhoticDetector()
    target = inventory.load("en", "es").target("r")          # same candidates/classes for r and ɾ
    pc = target.phone_class

    streams = []
    if args.cp_root or args.native_tsv:
        items = (corpora.common_phone(args.cp_root, args.lang, args.split, args.n) if args.cp_root
                 else corpora.tsv(args.native_tsv))
        streams.append(tokens(items, "spanish_mfa", "spanish_mfa", {"r": "trill", "ɾ": "tap"}, "native_es"))
    if args.english_tsv:
        streams.append(tokens(corpora.tsv(args.english_tsv), "english_mfa", "english_us_mfa",
                              {"ɹ": "english_r"}, "english"))

    rows = []
    for stream in streams:
        for t in stream:
            p = t["phone"]
            m = det.measure(t["x"], t["sr"], (p.start, p.end))
            evs = [comb.make_evidence("detector", de.id, de.version, de.status,
                                      det.scores(m, target.phones, pc), pc, de.params["margin"])]
            if rec is not None:
                sc, _un = candidate_scores(rec.posteriors(t["wav"]), window(p, re_.params["pad_s"]), target.phones)
                raw = max(sc.values(), default=0.0)
                evs.append(comb.make_evidence("recognizer", re_.id, re_.version, re_.status,
                                              sc if raw >= re_.params["min_raw"] else {}, pc,
                                              re_.params["margin"]))
            v = comb.combine(evs, pc)
            rows.append({"source": t["source"], "wav": Path(t["wav"]).name, "word": t["word"],
                         "context": t["context"], "label": t["label"],
                         "detector": evs[0].top_class if evs[0].decisive else "abstain",
                         "recognizer": (evs[1].top_class if evs[1].decisive else "abstain") if rec else None,
                         "recognizer_margin": evs[1].margin if rec else None,
                         "verdict": v["status"], "verdict_class": v["realised_class"],
                         "f3_ratio": m["f3_ratio"], "n_occlusions": m["n_occlusions"]})

    def confusion(key, subset):
        c = defaultdict(Counter)
        for r in subset:
            c[r["label"]][r[key] or "none"] += 1
        return {k: dict(v) for k, v in c.items()}

    non_coda = [r for r in rows if r["context"] != "coda"]
    confident = [r for r in non_coda if r["verdict"] == "confident"]
    summary = {
        "label": args.label, "date": dt.date.today().isoformat(),
        "sources": {"detector": f"{de.id} {de.version} (calibrated={load_calibration().get('calibrated')})",
                    "recognizer": None if rec is None else f"{re_.id} {re_.version}"},
        "n_tokens": dict(Counter(r["label"] for r in rows)),
        "non_coda": {"detector": confusion("detector", non_coda),
                     "recognizer": confusion("recognizer", non_coda) if rec else None,
                     "verdict_status": confusion("verdict", non_coda),
                     "confident_class": confusion("verdict_class", confident),
                     "confident_accuracy": (sum(r["verdict_class"] == r["label"] for r in confident) / len(confident))
                     if confident else None,
                     "confident_coverage": len(confident) / len(non_coda) if non_coda else None},
        "coda": {"verdict_class": confusion("verdict_class", [r for r in rows if r["context"] == "coda"])},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summary, "tokens": rows}, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
