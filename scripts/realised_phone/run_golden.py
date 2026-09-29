#!/usr/bin/env python3
"""
Run the realised-phone golden clips (tests/golden/realised_phone/manifest.yaml).

    MIO_MFA_CMD="conda run -n mfa mfa" MIO_MFA_MODELS=~/mfa_models \\
    MIO_GOLDEN_DIR=~/datasets/miolingo_golden CP_ROOT=~/datasets/common_phone/CP \\
    venv/bin/python scripts/realised_phone/run_golden.py --allow-candidates [--json out.json]

--allow-candidates is needed until models are approved (the run is a TEST of
candidates -- exactly the evidence Matthew reviews before approving).
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
from realised_phone.align import mfa_align  # noqa: E402
from realised_phone.detectors import DETECTORS  # noqa: E402
from realised_phone.pipeline import analyse  # noqa: E402

MANIFEST = ROOT / "tests" / "golden" / "realised_phone" / "manifest.yaml"


def _path(p: str) -> str:
    return os.path.expanduser(os.path.expandvars(p))


def run_clip(c: dict, allow_candidates: bool) -> dict:
    wav = _path(c["wav"])
    if c["id"].endswith("-TODO") or "$" in wav or not Path(wav).exists():
        return {"id": c["id"], "result": "skipped", "why": f"missing: {wav}"}
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
        m = det.measure(x, sr, (p.start, p.end))
        sc = det.scores(m, tgt.phones, tgt.phone_class)
        got = tgt.phone_class[max(sc, key=sc.get)] if sc else "abstain"
        ok = got == c["class"] or (got == "abstain" and c.get("abstain_ok"))
        return {"id": c["id"], "result": "pass" if ok else "fail", "expected": c["class"],
                "got": got, "measurements": m}
    a = analyse(wav, c["text"], c.get("l1", "en"), c.get("l2", "es"),
                transcript=c["text"], skip_gate=True, allow_candidates=allow_candidates)
    fails = []
    for exp in c["expect"]:
        v = next((v for v in a.verdicts if v.word == exp["word"] and v.target == inventory.norm_ipa(exp["target"])), None)
        if v is None:
            fails.append(f"no verdict for /{exp['target']}/ in {exp['word']}")
        elif "status" in exp and v.status != exp["status"]:
            fails.append(f"{exp['word']}: status {v.status} != {exp['status']}")
        elif "class" in exp and v.realised_class != exp["class"]:
            fails.append(f"{exp['word']}: {v.describe()} (expected {exp['class']})")
    return {"id": c["id"], "result": "fail" if fails else "pass", "why": fails, "notes": a.notes}


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
    counts = {k: sum(r["result"] == k for r in results) for k in ("pass", "fail", "skipped")}
    print(counts)
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str))
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
