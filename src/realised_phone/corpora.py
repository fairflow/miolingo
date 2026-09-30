"""
Corpus readers shared by the realised-phone scripts (native bank, calibration,
golden runs). Common Phone layout matches research/phonetics/phone_poc/cp_eval.py:
<cp_root>/<lang>/<split>.csv with columns "audio file", "text"; audio in wav/<stem>.wav.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterator


def common_phone(cp_root: str, lang: str, split: str = "test", n: int = 0) -> Iterator[dict]:
    d = Path(os.path.expanduser(cp_root)) / lang
    k = 0
    with (d / f"{split}.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            wav = d / "wav" / f"{Path(row['audio file']).stem}.wav"
            if wav.exists():
                yield {"wav": str(wav), "text": row["text"], "id": wav.stem,
                       "speaker": row.get("client_id") or row.get("speaker") or ""}
                k += 1
                if n and k >= n:
                    return


def tsv(path: str, n: int = 0) -> Iterator[dict]:
    """Lines 'wav<TAB>text[<TAB>speaker]' (relative paths resolved against the TSV's
    folder), e.g. list.tsv from scripts/realised_phone/extract_cp_parquet.py."""
    base = Path(path).parent
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        wav, text, *rest = line.split("\t")
        p = Path(os.path.expandvars(os.path.expanduser(wav)))
        p = p if p.is_absolute() else base / p
        yield {"wav": str(p), "text": text.strip(), "id": p.stem,
               "speaker": rest[0].strip() if rest else ""}
        n -= 1
        if n == 0:
            return
