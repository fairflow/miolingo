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
                yield {"wav": str(wav), "text": row["text"]}
                k += 1
                if n and k >= n:
                    return


def tsv(path: str) -> Iterator[dict]:
    """Lines 'wav<TAB>text' (relative paths resolved against the TSV's folder)."""
    base = Path(path).parent
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        wav, text = line.split("\t", 1)
        p = Path(os.path.expandvars(os.path.expanduser(wav)))
        yield {"wav": str(p if p.is_absolute() else base / p), "text": text.strip()}
