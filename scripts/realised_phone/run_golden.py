#!/usr/bin/env python3
"""
Run the realised-phone golden clips (tests/golden/realised_phone/manifest.yaml).

    MIO_MFA_CMD="conda run -n mfa mfa" MIO_MFA_MODELS=~/mfa_models \\
    MIO_GOLDEN_DIR=~/datasets/miolingo_golden CP_ROOT=~/datasets/common_phone/CP \\
    venv/bin/python scripts/realised_phone/run_golden.py --allow-candidates [--json out.json]

--allow-candidates is needed until models are approved (the run is a TEST of
candidates -- exactly the evidence Matthew reviews before approving).
Outcomes (accuracy of what the learner is shown outranks coverage):
  pass      verdict class matches the expected class
  abstain   uncertain / no evidence -- the system declined; not a failure
  soft_fail tentative verdict with the wrong class (never shown to learners)
  fail      confident verdict with the wrong class, or expectation not checkable
Exit status 1 if any present clip fails; missing clips are reported as skipped.
Clips whose id ends in -TODO are placeholders and always skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from realised_phone import inventory  # noqa: E402
from realised_phone import combine as comb  # noqa: E402
from realised_phone.align import mfa_align, window  # noqa: E402
from realised_phone.detectors import DETECTORS  # noqa: E402
from realised_phone.pipeline import analyse  # noqa: E402

MANIFEST = ROOT / "tests" / "golden" / "realised_phone" / "manifest.yaml"


def _path(p: str) -> str:
    return os.path.expanduser(os.path.expandvars(p))


def _after_stop(al, p) -> bool:
    from realised_phone.detectors.rhotic import is_stop
    i = al.phones.index(p)
    return i > 0 and p.start - al.phones[i - 1].end < 0.03 and is_stop(al.phones[i - 1].label)


def _outcome(status: str, got: str, expected: str) -> str:
    if status in ("uncertain", "no_evidence") or got in (None, "abstain"):
        return "abstain"
    if got == expected:
        return "pass"
    return "fail" if status == "confident" else "soft_fail"


def _combined(c: dict, wav: str, allow_candidates: bool) -> dict:
    """English-aligned token: detector + recognizer on the window, combined."""
    import soundfile as sf
    from realised_phone.recognizer import RecognizerSource, candidate_scores
    from realised_phone.registry import Registry
    al = mfa_align(wav, c["text"], c["aligner"]["acoustic_model"], c["aligner"]["dictionary"])
    hits = [p for p in al.phones if p.label == inventory.norm_ipa(c["phone"])]
    if len(hits) < c.get("occurrence", 1):
        return {"id": c["id"], "result": "fail", "why": f"only {len(hits)} [{c['phone']}] aligned"}
    p = hits[c.get("occurrence", 1) - 1]
    after_stop = _after_stop(al, p)
    x, sr = sf.read(wav, dtype="float64")
    x = x.mean(axis=1) if x.ndim > 1 else x
    from realised_phone.pipeline import source_for
    l1, l2 = c.get("pair", "en-es").split("-", 1)
    tgt = inventory.load(l1, l2).target(c.get("target", "r"))     # judged against this L2 target
    pc = tgt.phone_class
    reg = Registry.load()
    de = reg.require("rhotic-detector", allow_candidates)
    re_ = reg.require(source_for(reg, "recognizer", l2), allow_candidates)
    det = DETECTORS["rhotic"]()
    evs = [comb.make_evidence("detector", de.id, de.version, de.status,
                              det.scores(det.measure(x, sr, (p.start, p.end), after_stop), tgt.phones, pc), pc,
                              de.params["margin"])]
    try:
        sc, _ = candidate_scores(RecognizerSource(re_.id, re_.version).posteriors(wav),
                                 window(p, re_.params["pad_s"]), tgt.phones)
        if max(sc.values(), default=0) >= re_.params["min_raw"]:
            evs.append(comb.make_evidence("recognizer", re_.id, re_.version, re_.status, sc, pc,
                                          re_.params["margin"]))
    except Exception as ex:  # noqa: BLE001 - recognizer optional
        note = f"recognizer unavailable: {ex}"
    else:
        note = ""
    v = comb.combine(evs, pc)
    got = v["realised_class"]
    return {"id": c["id"], "result": _outcome(v["status"], got, c["class"]), "expected": c["class"],
            "got": got or f"uncertain {v['between']}", "status": v["status"], "note": note}


def run_clip(c: dict, allow_candidates: bool) -> dict:
    wav = _path(c["wav"])
    if c["id"].endswith("-TODO") or "$" in wav or not Path(wav).exists():
        return {"id": c["id"], "result": "skipped", "why": f"missing: {wav}"}
    if c["level"] == "combined":
        return _combined(c, wav, allow_candidates)
    if c["level"] == "detector":
        import soundfile as sf
        al = mfa_align(wav, c["text"], c["aligner"]["acoustic_model"], c["aligner"]["dictionary"])
        hits = [p for p in al.phones if p.label == inventory.norm_ipa(c["phone"])]
        if len(hits) < c.get("occurrence", 1):
            return {"id": c["id"], "result": "fail", "why": f"only {len(hits)} [{c['phone']}] aligned"}
        p = hits[c.get("occurrence", 1) - 1]
        x, sr = sf.read(wav, dtype="float64")
        tgt = inventory.load("en", "es").target("r")        # rhotic candidate classes
        det = DETECTORS[c["detector"]]()
        m = det.measure(x, sr, (p.start, p.end), _after_stop(al, p))
        sc = det.scores(m, tgt.phones, tgt.phone_class)
        got = tgt.phone_class[max(sc, key=sc.get)] if sc else "abstain"
        ok = got == c["class"] or (got == "abstain" and c.get("abstain_ok"))
        return {"id": c["id"], "result": "pass" if ok else "fail", "expected": c["class"],
                "got": got, "measurements": m}
    a = analyse(wav, c["text"], c.get("l1", "en"), c.get("l2", "es"),
                transcript=c["text"], skip_gate=True, allow_candidates=allow_candidates)
    outcomes, why = [], []
    for exp in c["expect"]:
        v = next((v for v in a.verdicts if v.word == exp["word"] and v.target == inventory.norm_ipa(exp["target"])), None)
        if v is None:
            outcomes.append("fail")
            why.append(f"no verdict for /{exp['target']}/ in {exp['word']} ({'; '.join(a.notes)})")
        elif "status" in exp:
            ok = v.status == exp["status"]
            outcomes.append("pass" if ok else "fail")
            if not ok:
                why.append(f"{exp['word']}: status {v.status} != {exp['status']}")
        else:
            o = _outcome(v.status, v.realised_class, exp["class"])
            outcomes.append(o)
            if o != "pass":
                why.append(f"{exp['word']}: {v.describe()} (expected {exp['class']})")
    order = ["fail", "soft_fail", "abstain", "pass"]
    worst = min(outcomes, key=order.index) if outcomes else "fail"
    return {"id": c["id"], "result": worst, "why": why, "notes": a.notes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--allow-candidates", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    clips = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))["clips"]
    results = [run_clip(c, args.allow_candidates) for c in clips]
    for r in results:
        print(f"{r['result']:8s} {r['id']}  {r.get('got', '')} {r.get('why', '')}")
    counts = {k: sum(r["result"] == k for r in results)
              for k in ("pass", "abstain", "soft_fail", "fail", "skipped")}
    print(counts)
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str))
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
