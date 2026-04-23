#!/usr/bin/env python3
"""Generate language_materials/en/words/ from unified phrases JSON.

Produces per-level wordlists + a complete dictionary, following the
`word | translation | [ipa]` format used by other languages' words/ files.

Level mapping (mirrors pt/words/ convention, chronological unified files):
    A -> common-phrases-001.json
    B -> common-phrases-003.json
    C -> common-phrases-004.json
    D -> common-phrases-005.json  (no Portuguese)

Translation column is left blank in every row (Option 2 semantics: NULL
source language / translation = unspecified, to be enriched). This avoids
baking in any particular source-language bias and mirrors the Tier 3 plan
in project memory (`project_personal_vocab.md`) — eventually vocabulary
rows will hold a map of translations per source language.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIFIED = ROOT / "language_materials" / "unified" / "phrases"
OUT = ROOT / "language_materials" / "en" / "words"

LEVEL_FILES = [
    ("A", "001", "common-phrases-001.json"),
    ("B", "002", "common-phrases-003.json"),
    ("C", "003", "common-phrases-004.json"),
    ("D", "004", "common-phrases-005.json"),
]

# Cheap tokeniser: letters + apostrophes, lowercase.
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'']*")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text or "")]


def load_phrases(path: Path) -> list[dict]:
    return json.loads(path.read_text())["phrases"]


_ipa_cache: dict[str, str] = {}


def word_ipa(word: str) -> str:
    """Per-word English IPA via espeak. Cached; empty string on failure."""
    if word in _ipa_cache:
        return _ipa_cache[word]
    try:
        res = subprocess.run(
            ["espeak", "-v", "en", "--ipa", "-q", word],
            capture_output=True, text=True, timeout=5,
        )
        ipa = res.stdout.strip()
    except Exception:
        ipa = ""
    _ipa_cache[word] = ipa
    return ipa


def extract_level(json_path: Path) -> dict[str, dict]:
    """Return { en_word: {translation, ipa} } for one level file.

    - Tokenises every English phrase in the file, collecting all unique words.
    - IPA is generated per-word via espeak (not the containing-phrase IPA).
    - Translation is left blank: phrase-level pt translations don't cleanly
      map onto single English tokens, and blank is the Option-2-correct
      value meaning "unspecified, enrich me".
    """
    out: dict[str, dict] = {}
    for ph in load_phrases(json_path):
        en = (ph.get("text", {}).get("en") or "").strip()
        if not en:
            continue
        for tok in tokenize(en):
            if tok not in out:
                out[tok] = {"translation": "", "ipa": word_ipa(tok)}
    return out


def write_wordlist(path: Path, words: dict[str, dict], header: list[str]) -> None:
    lines = [f"# {h}" for h in header] + [""]
    for word in sorted(words):
        tr = words[word]["translation"] or ""
        ipa = words[word]["ipa"] or ""
        ipa_col = f" | [{ipa}]" if ipa else ""
        lines.append(f"{word} | {tr}{ipa_col}")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    seen: dict[str, dict] = {}
    for level, num, fname in LEVEL_FILES:
        words = extract_level(UNIFIED / fname)
        # Merge into running dictionary (first-seen wins, matches level ordering).
        for w, info in words.items():
            seen.setdefault(w, info)
        out_path = OUT / f"words-{num}.txt"
        write_wordlist(
            out_path,
            words,
            [
                f"English words from {fname}",
                f"Level: {level}",
                f"Total unique words: {len(words)}",
                "",
                "Translation column blank by design (Option 2 semantics).",
                "Format: word | translation | [ipa]",
            ],
        )
        print(f"wrote {out_path} ({len(words)} words)")

    dict_path = OUT / "dictionary-complete.txt"
    write_wordlist(
        dict_path,
        seen,
        [
            "Complete English Dictionary",
            "Generated from unified common-phrases files",
            f"Total words: {len(seen)}",
            "",
            "Translation column blank by design (Option 2 semantics).",
            "Format: word | translation | [ipa]",
        ],
    )
    print(f"wrote {dict_path} ({len(seen)} words)")


if __name__ == "__main__":
    main()
