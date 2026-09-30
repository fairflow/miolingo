#!/usr/bin/env python3
"""
Extract Common Phone utterances from the author's Hugging Face Parquet release
(pklumpp/CommonPhoneDataset, CC0) -- an alternative to the 13 GB Zenodo tarball
when only a language or two is needed.

Writes <out>/<lang>/<split>/<utt>.wav, list.tsv (wav<TAB>text<TAB>speaker) and
labels/<utt>.json (Common Phone's own time-aligned IPA: [[start, end, symbol], ...]).
Caps utterances per speaker so a few prolific speakers don't dominate.

    curl -L -o dev-2.parquet https://huggingface.co/datasets/pklumpp/CommonPhoneDataset/resolve/main/data/dev-00002-of-00004.parquet
    venv/bin/python scripts/realised_phone/extract_cp_parquet.py dev-*.parquet --lang es --split dev --out ~/datasets/cp_hf --n 400
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parquet", nargs="+")
    ap.add_argument("--lang", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=0, help="max utterances (0 = all)")
    ap.add_argument("--per-speaker", type=int, default=3)
    args = ap.parse_args()

    import pyarrow.parquet as pq

    out = Path(args.out).expanduser() / args.lang / args.split
    (out / "labels").mkdir(parents=True, exist_ok=True)
    per = Counter()
    lines, k = [], 0
    for path in args.parquet:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=64):
            for r in batch.to_pylist():
                if r["language"] != args.lang or per[r["speaker"]] >= args.per_speaker:
                    continue
                stem = Path(r["audio"]["path"]).stem
                (out / f"{stem}.wav").write_bytes(r["audio"]["bytes"])
                (out / "labels" / f"{stem}.json").write_text(json.dumps(
                    [[l["start"], l["end"], l["symbol"]] for l in r["labels"]], ensure_ascii=False),
                    encoding="utf-8")
                lines.append(f"{stem}.wav\t{r['text'].strip()}\t{r['speaker']}")
                per[r["speaker"]] += 1
                k += 1
                if args.n and k >= args.n:
                    break
            if args.n and k >= args.n:
                break
        if args.n and k >= args.n:
            break
    (out / "list.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{k} utterances from {len(per)} speakers -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
