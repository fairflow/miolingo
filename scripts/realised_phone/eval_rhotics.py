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
from realised_phone.align import window  # noqa: E402
from realised_phone.pipeline import source_for  # noqa: E402
from realised_phone.tokens import EN_LABELS, ES_LABELS, FR_LABELS, rhotic_tokens  # noqa: E402

# language of the SPEECH in a token list -> (aligner model, dictionary, phone -> label) per
# target detector. Label "native" = a native speaker's own target sound: counted correct when
# the verdict is any class accepted for the token's context (e.g. Dutch r: trill/tap/uvular).
PROFILES = {
    "rhotic": {"es": ("spanish_mfa", "spanish_mfa", ES_LABELS),
               "en": ("english_mfa", "english_us_mfa", EN_LABELS),
               "fr": ("french_mfa", "french_mfa", FR_LABELS),
               "nl": ("dutch_cv", "dutch_cv", {"r": "native"})},
    "dorsal": {"nl": ("dutch_cv", "dutch_cv", {"x": "native", "ɣ": "native"}),
               "en": ("english_mfa", "english_us_mfa", {"kʰ": "stop", "k": "stop", "ɡ": "stop", "h": "glottal"})},
}
from realised_phone.detectors import DETECTORS  # noqa: E402
from realised_phone.detectors.rhotic import is_stop, load_calibration  # noqa: E402
from realised_phone.recognizer import RecognizerSource, candidate_scores  # noqa: E402
from realised_phone.registry import Registry  # noqa: E402


def _cached_posteriors(cache_dir: str):
    """Wrap ctc_posteriors with an on-disk cache so repeated evaluations (e.g. two
    calibrations) don't re-run the recognizer."""
    import numpy as np
    from realised_phone.recognizer import Posteriors, ctc_posteriors

    d = Path(cache_dir)
    d.mkdir(parents=True, exist_ok=True)

    def fn(model_id: str, wav: str) -> Posteriors:
        f = d / f"{model_id.replace('/', '__')}__{Path(wav).stem}.npz"
        if f.exists():
            z = np.load(f, allow_pickle=False)
            return Posteriors(z["probs"], dict(zip(z["tokens"].tolist(), z["cols"].tolist())))
        p = ctc_posteriors(model_id, wav)
        toks = list(p.vocab)
        np.savez_compressed(f, probs=p.probs.astype(np.float16), tokens=np.array(toks),
                            cols=np.array([p.vocab[t] for t in toks]))
        return p
    return fn


def _correct(label: str, verdict_class, target, context: str, own_target=None) -> bool:
    """'native' tokens are judged against THEIR OWN target phone when the inventory has one
    (a Flemish ch [x] against /x/, not against /ɣ/), else against the evaluated target."""
    if label == "native":
        t = own_target or target
        return verdict_class in t.accepted_classes(context)
    return verdict_class == label


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cp-root")
    ap.add_argument("--native-tsv")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--split", default="test")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--english-tsv")
    ap.add_argument("--en-cp", action="store_true", help="English [ɹ] tokens from Common Phone en")
    ap.add_argument("--en-n", type=int, default=150)
    ap.add_argument("--cache", default=None, help="alignment cache dir (reused across runs)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--label", required=True, help="short name of this evaluation set")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-recognizer", action="store_true")
    ap.add_argument("--calibration", help="rhotic calibration YAML to evaluate (default: shipped)")
    ap.add_argument("--post-cache", help="dir to cache recognizer posteriors (.npz per utterance)")
    ap.add_argument("--pair", default="en-es", help="L1-L2 whose inventory/recognizer to evaluate")
    ap.add_argument("--target", default="r", help="target phone in the L2 inventory (r for es, ʁ for fr, ɹ for en)")
    ap.add_argument("--recognizer", help="registry id to use instead of the L2's first recognizer")
    ap.add_argument("--tokens", action="append", default=[], metavar="LANG=TSV",
                    help="token list whose speech is in LANG (es/en/fr); repeatable. E.g. for en-fr: "
                         "fr=<native French> en=<English speech as the English-r stand-in>")
    args = ap.parse_args()
    l1, l2 = args.pair.split("-", 1)

    reg = Registry.load()
    re_ = reg.get(args.recognizer or source_for(reg, "recognizer", l2))
    pair_inv = inventory.load(l1, l2)
    target = pair_inv.target(args.target)
    de = reg.get(f"{target.detector}-detector")
    rec = None if args.no_recognizer else RecognizerSource(
        re_.id, re_.version, posterior_fn=_cached_posteriors(args.post_cache) if args.post_cache else None)
    import yaml
    det_cls = DETECTORS[target.detector]
    cal = (yaml.safe_load(Path(args.calibration).read_text(encoding="utf-8")) if args.calibration
           else det_cls().cal)
    det = det_cls(cal)
    # candidates/classes of the target (for es, r and ɾ share them)
    pc = target.phone_class

    kw = dict(cache_dir=args.cache, jobs=args.jobs)
    streams = []
    if args.cp_root or args.native_tsv:
        items = (corpora.common_phone(args.cp_root, args.lang, args.split, args.n) if args.cp_root
                 else corpora.tsv(args.native_tsv))
        streams.append(rhotic_tokens(items, "spanish_mfa", "spanish_mfa", ES_LABELS, "native_es", **kw))
    if args.en_cp and args.cp_root:
        streams.append(rhotic_tokens(corpora.common_phone(args.cp_root, "en", args.split, args.en_n),
                                     "english_mfa", "english_us_mfa", EN_LABELS, "english", **kw))
    if args.english_tsv:
        streams.append(rhotic_tokens(corpora.tsv(args.english_tsv), "english_mfa", "english_us_mfa",
                                     EN_LABELS, "english", **kw))

    for spec in args.tokens:
        lang, tsv = spec.split("=", 1)
        override = None
        if ":" in tsv:                    # LANG=TSV:phone=label,phone=label (explicit labels)
            tsv, mp = tsv.rsplit(":", 1)
            override = dict(kv.split("=", 1) for kv in mp.split(","))
        am, dic, labels = PROFILES.get(target.detector, PROFILES["rhotic"]).get(lang) or \
            (*{"fr": ("french_mfa", "french_mfa"), "en": ("english_mfa", "english_us_mfa"),
               "es": ("spanish_mfa", "spanish_mfa"), "nl": ("dutch_cv", "dutch_cv")}[lang], {})
        labels = override or labels
        excl = ("coda",) if (lang == "en" and target.detector == "rhotic") else ()  # non-rhotic accents drop coda [ɹ]
        streams.append(rhotic_tokens(corpora.tsv(tsv), am, dic, labels, f"{lang}_speech",
                                     exclude_contexts=excl, **kw))

    rows = []
    for stream in streams:
        for t in stream:
            p = t["phone"]
            m = det.measure(t["x"], t["sr"], (p.start, p.end), after_stop=is_stop(t.get("prev", "")))
            evs = [comb.make_evidence("detector", de.id, de.version, de.status,
                                      det.scores(m, target.phones, pc), pc, de.params["margin"])]
            if rec is not None:
                sc, _un = candidate_scores(rec.posteriors(t["wav"]), window(p, re_.params["pad_s"]), target.phones)
                raw = max(sc.values(), default=0.0)
                evs.append(comb.make_evidence("recognizer", re_.id, re_.version, re_.status,
                                              sc if raw >= re_.params["min_raw"] else {}, pc,
                                              re_.params["margin"]))
            v = comb.combine(evs, pc)
            rows.append({"source": t["source"], "wav": Path(t["wav"]).name, "speaker": t["speaker"],
                         "start": round(p.start, 3), "end": round(p.end, 3), "word": t["word"],
                         "context": t["context"], "label": t["label"],
                         "detector": evs[0].top_class if evs[0].decisive else "abstain",
                         "recognizer": (evs[1].top_class if evs[1].decisive else "abstain") if rec else None,
                         "recognizer_margin": evs[1].margin if rec else None,
                         "verdict": v["status"], "verdict_class": v["realised_class"],
                         "phone": p.label,
                         "correct": _correct(t["label"], v["realised_class"], target, t["context"],
                                             pair_inv.target(p.label)),
                         **{k: m.get(k) for k in ("f3_ratio", "n_occlusions", "closure_db", "spread_db",
                                                  "voiced_fraction")}})

    def confusion(key, subset):
        c = defaultdict(Counter)
        for r in subset:
            c[r["label"]][r[key] or "none"] += 1
        return {k: dict(v) for k, v in c.items()}

    non_coda = [r for r in rows if r["context"] != "coda"]
    confident = [r for r in non_coda if r["verdict"] == "confident"]
    summary = {
        "label": args.label, "date": dt.date.today().isoformat(),
        "pair": args.pair, "target": args.target, "accepted_classes": target.accepted_classes("intervocalic"),
        "sources": {"detector": f"{de.id} {de.version} (calibrated={cal.get('calibrated')}, "
                                    f"calibration={args.calibration or 'shipped'})",
                    "recognizer": None if rec is None else f"{re_.id} {re_.version}"},
        "n_tokens": dict(Counter(r["label"] for r in rows)),
        "n_speakers": {src: len({r["speaker"] for r in rows if r["source"] == src and r["speaker"]})
                       for src in {r["source"] for r in rows}},
        "non_coda": {"detector": confusion("detector", non_coda),
                     "recognizer": confusion("recognizer", non_coda) if rec else None,
                     "verdict_status": confusion("verdict", non_coda),
                     "confident_class": confusion("verdict_class", confident),
                     "confident_accuracy": (sum(r["correct"] for r in confident) / len(confident))
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
