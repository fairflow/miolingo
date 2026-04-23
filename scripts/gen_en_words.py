#!/usr/bin/env python3
"""Generate language_materials/en/words/ by inverting pt/words/.

Each pt/words file already has `pt_word | english_translation | [pt_ipa]`
triples. Inverting them yields exactly what we want for an en/words file
when the user's source language is Portuguese:

    english_word | pt_word | [en_ipa]

Per-word English IPA is generated with espeak (the pt IPA in the input
is the Portuguese pronunciation, not useful for English targets).

If multiple Portuguese words share the same English translation
(e.g. "bom", "boa", "bem" all → "good"), the English word gets the
first-seen Portuguese translation; duplicates are dropped on the
English side.

Outputs:
  words-001.txt  (from pt/words/words-001.txt, level A)
  words-002.txt  (from pt/words/words-002.txt, level B)
  words-003.txt  (from pt/words/words-003.txt, level C)
  words-004.txt  (from pt/words/words-004.txt, level D)
  dictionary-complete.txt  (from pt/words/dictionary-complete.txt)

Note: source language for the translation column is Portuguese. This is
the Tier-2-era compromise; Tier 3 will store per-source translations.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PT_WORDS = ROOT / "language_materials" / "pt" / "words"
OUT = ROOT / "language_materials" / "en" / "words"

LEVEL_FILES = [
    ("A", "001", "words-001.txt"),
    ("B", "002", "words-002.txt"),
    ("C", "003", "words-003.txt"),
    ("D", "004", "words-004.txt"),
]

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'']*")
_ipa_cache: dict[str, str] = {}


def word_ipa(word: str) -> str:
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


def parse_pt_file(path: Path) -> list[tuple[str, str]]:
    """Read a pt/words file → list of (pt_word, english_translation)."""
    pairs: list[tuple[str, str]] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        pt_word, english = parts[0], parts[1]
        if not pt_word or not english:
            continue
        pairs.append((pt_word, english))
    return pairs


def invert(pairs: list[tuple[str, str]]) -> dict[str, dict]:
    """Invert pt→en pairs into { en_word: {translation (pt), ipa (en)} }.

    English translations may contain multiple words or whitespace + casing
    variants ("Of course", "good"). We take the first token of the English
    translation, lowercased, as the key — this is what a single-word
    dictionary entry should be. Multi-word English translations (e.g.
    "thank you") are skipped in the per-level files but kept in the
    complete dictionary by collapsing them onto their first token.
    """
    out: dict[str, dict] = {}
    for pt_word, english in pairs:
        # Whole-English-phrase → single-token key is lossy, so instead we
        # keep only entries whose English side is itself a single token.
        toks = WORD_RE.findall(english)
        if len(toks) != 1:
            continue
        key = toks[0].lower()
        if key in out:
            continue  # first seen wins
        out[key] = {"translation": pt_word, "ipa": word_ipa(key)}
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

    for level, num, fname in LEVEL_FILES:
        src = PT_WORDS / fname
        pairs = parse_pt_file(src)
        words = invert(pairs)
        write_wordlist(
            OUT / f"words-{num}.txt",
            words,
            [
                f"English words derived from pt/words/{fname}",
                f"Level: {level}",
                f"Total unique words: {len(words)}",
                "",
                "Source language (translation column): Portuguese (pt)",
                "Format: word | translation | [ipa]",
            ],
        )
        print(f"wrote words-{num}.txt ({len(words)} words)")

    src = PT_WORDS / "dictionary-complete.txt"
    pairs = parse_pt_file(src)
    words = invert(pairs)
    write_wordlist(
        OUT / "dictionary-complete.txt",
        words,
        [
            "Complete English Dictionary",
            "Derived from pt/words/dictionary-complete.txt",
            f"Total words: {len(words)}",
            "",
            "Source language (translation column): Portuguese (pt)",
            "Format: word | translation | [ipa]",
        ],
    )
    print(f"wrote dictionary-complete.txt ({len(words)} words)")


if __name__ == "__main__":
    main()
