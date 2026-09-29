#!/usr/bin/env python3
"""
Build the native-exemplar bank for the see/hear view (HANDOFF §2): align native
utterances with MFA, cut every word that contains a target phone of the pair
inventory, and save <bank>/<l2>/<word>.wav + <word>.json (word-local MFA JSON).

    MIO_MFA_CMD="conda run -n mfa mfa" \\
    venv/bin/python scripts/realised_phone/build_native_bank.py \\
        --cp-root ~/datasets/common_phone/CP --lang es --split train --n 2000 \\
        --bank ~/datasets/miolingo_native_bank

Then set MIO_NATIVE_BANK=~/datasets/miolingo_native_bank for the app.
Keeps the first --per-word exemplars per word (default 1); skips words already in the bank.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from realised_phone import corpora, inventory  # noqa: E402
from realised_phone.align import AlignmentError, mfa_align  # noqa: E402
from realised_phone.registry import Registry  # noqa: E402
from realised_phone.pipeline import ALIGNER_FOR  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--cp-root")
    src.add_argument("--tsv", help="wav<TAB>text list")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--l1", default="en", help="pair inventory whose targets to collect")
    ap.add_argument("--split", default="train")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--pad", type=float, default=0.04)
    ap.add_argument("--targets", default="", help="comma list; default: all detector targets")
    args = ap.parse_args()

    import soundfile as sf

    pair = inventory.load(args.l1, args.lang)
    wanted = ([t.strip() for t in args.targets.split(",") if t.strip()]
              or [k for k, t in pair.targets.items() if t.detector])
    ae = Registry.load().get(ALIGNER_FOR[args.lang])
    out = Path(args.bank).expanduser() / args.lang
    out.mkdir(parents=True, exist_ok=True)
    items = (corpora.common_phone(args.cp_root, args.lang, args.split, args.n) if args.cp_root
             else corpora.tsv(args.tsv))
    saved = 0
    for it in items:
        try:
            al = mfa_align(it["wav"], it["text"], ae.params["acoustic_model"], ae.params["dictionary"])
        except AlignmentError as e:
            print(f"skip {it['wav']}: {e}", file=sys.stderr)
            continue
        x, sr = sf.read(it["wav"], dtype="float64")
        for wi, w in enumerate(al.words):
            phs = al.phones_of_word(wi)
            if not any(p.label in wanted for p in phs) or (out / f"{w.label}.wav").exists():
                continue
            s0 = max(0.0, w.start - args.pad)
            s1 = min(len(x) / sr, w.end + args.pad)
            sf.write(out / f"{w.label}.wav", x[int(s0 * sr):int(s1 * sr)], sr, subtype="PCM_16")
            rel = lambda t: round(t - s0, 4)  # noqa: E731
            (out / f"{w.label}.json").write_text(json.dumps({
                "source": it["wav"], "text": it["text"], "aligner": ae.id, "version": ae.version,
                "tiers": {"words": {"entries": [[rel(w.start), rel(w.end), w.label]]},
                          "phones": {"entries": [[rel(p.start), rel(p.end), p.label] for p in phs]}}},
                ensure_ascii=False), encoding="utf-8")
            saved += 1
    print(f"saved {saved} exemplar words to {out}")


if __name__ == "__main__":
    main()
