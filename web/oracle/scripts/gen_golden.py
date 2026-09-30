#!/usr/bin/env python3
"""Generate golden-parity fixtures: the Python originals' outputs over a fixed
case list, committed to web/app/test/golden/ and asserted byte-for-byte by
golden.spec.ts. Regenerating these files is the ONLY sanctioned way to change
the TS reimplementations' behaviour.

Run: venv/bin/python web/oracle/scripts/gen_golden.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from scoring.comparison import (  # noqa: E402
    compare_phonemes_edit_distance,
    get_edit_operations,
    levenshtein_distance,
)
from ipa import fold_map  # noqa: E402

OUT = REPO / "web" / "app" / "test" / "golden"
OUT.mkdir(parents=True, exist_ok=True)

# Deliberately covers: ASCII, IPA with multi-codepoint segments, combining
# marks (ɛ̃ = 2 code points — the Swift-vs-Python divergence), empties, and
# the spec's kitten/sitting row.
CASES: list[tuple[str, str]] = [
    ("kitten", "sitting"),
    ("", ""),
    ("abc", ""),
    ("", "abc"),
    ("ʃa", "ʃa"),
    ("ʃjɛ̃", "ʃjɛ"),
    ("bɔ̃ʒuʁ", "bɔ̃ʒyʁ"),
    ("kom", "kɔm"),
    ("obɾiɡadʊ", "obɾiɡˈadu"),
    ("a b c", "abc"),
]


def comparison_golden() -> dict:
    cases = []
    for user, correct in CASES:
        exact, similarity, distance = compare_phonemes_edit_distance(user, correct)
        cases.append({
            "user": user,
            "correct": correct,
            "levenshtein": levenshtein_distance(user, correct),
            "exact": exact,
            "similarity": similarity,
            "distance": distance,
            # target-oriented ops: get_edit_operations(correct, user), '-' → ''
            "ops": [
                {
                    "op": op,
                    "target": "" if op == "insert" else c1,
                    "user": "" if op == "delete" else c2,
                }
                for op, _pos, c1, c2 in get_edit_operations(correct, user)
            ],
        })
    return {"generator": "web/oracle/scripts/gen_golden.py", "cases": cases}


def foldmap_golden() -> dict:
    langs = fold_map.languages()
    checks = []
    for lang in langs:
        pairs = sorted(
            [sorted(p) for p in (set(fs) for fs in fold_map.tolerated_pairs(lang))],
        )[:10]
        for a, b in pairs:
            checks.append({"lang": lang, "a": a, "b": b, "tolerated": True})
        inv = fold_map.inventory(lang)
        if len(inv) >= 2:
            # a same-language non-pair (first two inventory segs unless tolerated)
            a, b = inv[0], inv[1]
            checks.append({"lang": lang, "a": a, "b": b,
                           "tolerated": fold_map.is_tolerated(lang, a, b)})
    return {"generator": "web/oracle/scripts/gen_golden.py",
            "languages": langs, "checks": checks}


def main() -> None:
    (OUT / "comparison.json").write_text(
        json.dumps(comparison_golden(), ensure_ascii=False, indent=1) + "\n", "utf-8")
    (OUT / "foldmap.json").write_text(
        json.dumps(foldmap_golden(), ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"wrote {OUT}/comparison.json and foldmap.json")


if __name__ == "__main__":
    main()
