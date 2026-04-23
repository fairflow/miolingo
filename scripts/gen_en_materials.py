#!/usr/bin/env python3
"""Generate language_materials/en/ by inverting the French materials.

Mirrors the fr/ directory layout (phrases/, phrasebook-topics/,
phrasebook_complete.json, phrasebook_raw.json, story-phrases.txt,
metadata.json, update_ipa.sh). Content is derived by flipping each
triple `french | english | [fr_ipa]` into `english | french | [en_ipa]`
and regenerating IPA per phrase via espeak.

Skipped (no corresponding English source content):
    story.md, story-scenes-json/, story-critical-analysis.md.

Not regenerated here:
    words/  — see scripts/gen_en_words.py (derives from pt/words/).

Translation column source language is French (fr) — a Tier-2 compromise;
Tier 3 will let a single row hold translations for multiple sources.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FR = ROOT / "language_materials" / "fr"
EN = ROOT / "language_materials" / "en"

_ipa_cache: dict[str, str] = {}


def en_ipa(text: str) -> str:
    """English IPA for a phrase via espeak. Cached."""
    if not text:
        return ""
    if text in _ipa_cache:
        return _ipa_cache[text]
    try:
        res = subprocess.run(
            ["espeak", "-v", "en", "--ipa", "-q", text],
            capture_output=True, text=True, timeout=5,
        )
        # espeak emits newlines mid-phrase on punctuation; collapse to spaces.
        ipa = " ".join(res.stdout.split())
    except Exception:
        ipa = ""
    _ipa_cache[text] = ipa
    return ipa


def invert_triple_file(src: Path, dst: Path, header_rewrite: dict[str, str]) -> int:
    """Copy src → dst, inverting data lines and rewriting # header strings.

    header_rewrite: substitutions applied to comment lines (e.g.
    "french | english" → "english | french").

    Data lines whose English side already appears (first-seen-wins) or
    whose English side is empty are dropped.
    """
    out_lines: list[str] = []
    seen_en: set[str] = set()
    for raw in src.read_text().splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            out_lines.append("")
            continue
        if stripped.startswith("#"):
            for k, v in header_rewrite.items():
                line = line.replace(k, v)
            out_lines.append(line)
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            out_lines.append(line)  # preserve malformed lines verbatim
            continue
        fr_text, en_text = parts[0], parts[1]
        if not en_text:
            continue
        # Dedupe by lowercased english; first seen wins.
        key = en_text.lower()
        if key in seen_en:
            continue
        seen_en.add(key)
        ipa = en_ipa(en_text)
        ipa_col = f" | [{ipa}]" if ipa else ""
        out_lines.append(f"{en_text} | {fr_text}{ipa_col}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out_lines) + "\n")
    return sum(1 for ln in out_lines if ln and not ln.lstrip().startswith("#"))


HEADER_REWRITE = {
    "french | english": "english | french",
    "French Phrasebook": "English Phrasebook (from French)",
    "French phrases": "English phrases (derived from French)",
}


def do_phrases() -> None:
    src_dir = FR / "phrases"
    dst_dir = EN / "phrases"
    for src in sorted(src_dir.glob("phrases-*.txt")):
        dst = dst_dir / src.name
        n = invert_triple_file(src, dst, HEADER_REWRITE)
        print(f"wrote {dst.relative_to(ROOT)} ({n} entries)")


def do_topics() -> None:
    src_dir = FR / "phrasebook-topics"
    dst_dir = EN / "phrasebook-topics"
    for src in sorted(src_dir.glob("*.txt")):
        dst = dst_dir / src.name
        n = invert_triple_file(src, dst, HEADER_REWRITE)
        print(f"wrote {dst.relative_to(ROOT)} ({n} entries)")


def do_story_phrases() -> None:
    src = FR / "story-phrases.txt"
    dst = EN / "story-phrases.txt"
    n = invert_triple_file(src, dst, HEADER_REWRITE)
    print(f"wrote {dst.relative_to(ROOT)} ({n} entries)")


def do_phrasebook_json(raw: bool) -> None:
    name = "phrasebook_raw.json" if raw else "phrasebook_complete.json"
    src = FR / name
    dst = EN / name
    data = json.loads(src.read_text())
    meta = data.get("metadata", {})
    meta["source"] = (
        f"Derived from fr/{name} by inverting french/english columns."
    )
    new_phrases = []
    seen: set[str] = set()
    for ph in data.get("phrases", []):
        en = ph.get("english", "")
        fr = ph.get("french", "")
        if not en or not fr:
            continue
        key = en.lower()
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "english": en,
            "situation": ph.get("situation", ""),
            "level": ph.get("level", ""),
            "id": ph.get("id"),
            "french": fr,
        }
        if not raw:
            entry["ipa"] = en_ipa(en).lstrip("[").rstrip("]")
        new_phrases.append(entry)
    dst.write_text(json.dumps(
        {"metadata": meta, "phrases": new_phrases},
        ensure_ascii=False, indent=2,
    ) + "\n")
    print(f"wrote {dst.relative_to(ROOT)} ({len(new_phrases)} phrases)")


def do_metadata() -> None:
    dst = EN / "metadata.json"
    meta = {
        "language_code": "en",
        "language_name": "English",
        "structure": {
            "difficulty_levels": 4,
            "files_per_level": 5,
            "phrases_per_file": 50,
            "total_capacity": 1000,
        },
        "current_content": {
            "source": "Derived from fr/ by inverting french/english columns.",
            "note": (
                "Translation column is French. Tier 3 will add multi-source "
                "translations (project memory: project_personal_vocab.md)."
            ),
            "populated": [
                "phrases/phrases-00{1,3,4,5}.txt",
                "phrasebook-topics/*.txt",
                "phrasebook_complete.json",
                "phrasebook_raw.json",
                "story-phrases.txt",
                "words/ (derived separately from pt/words/)",
            ],
            "not_populated": [
                "story.md (no English source story)",
                "story-scenes-json/ (depends on en story)",
                "story-critical-analysis.md (French-specific analysis)",
            ],
        },
        "format": "phrase | translation | [ipa]",
        "ipa_source": "espeak -v en --ipa",
        "version": "1.0",
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {dst.relative_to(ROOT)}")


def do_update_ipa_sh() -> None:
    dst = EN / "update_ipa.sh"
    dst.write_text("""#!/bin/bash
# Regenerate IPA for every English phrase/word file under this directory
# using espeak. Run from this directory.
set -euo pipefail

if ! command -v espeak >/dev/null 2>&1; then
    echo "Error: espeak not found." >&2
    exit 1
fi

ipa() { espeak -v en --ipa -q "$1" 2>/dev/null | tr -d '\\n'; }

process() {
    local file="$1"
    local tmp="${file}.tmp"
    : > "$tmp"
    while IFS= read -r line; do
        case "$line" in
            '#'*|'') echo "$line" >> "$tmp"; continue;;
        esac
        IFS='|' read -r text tr _ <<< "$line"
        text=$(echo "$text" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        tr=$(echo "$tr" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        new_ipa=$(ipa "$text")
        echo "$text | $tr | [$new_ipa]" >> "$tmp"
    done < "$file"
    mv "$tmp" "$file"
    echo "  updated $file"
}

for f in phrases/*.txt phrasebook-topics/*.txt story-phrases.txt; do
    [ -f "$f" ] && process "$f"
done
echo "done."
""")
    dst.chmod(0o755)
    print(f"wrote {dst.relative_to(ROOT)}")


def main() -> None:
    EN.mkdir(exist_ok=True)
    do_metadata()
    do_phrases()
    do_topics()
    do_story_phrases()
    do_phrasebook_json(raw=False)
    # phrasebook_raw.json is French-only (no english field); skip inversion.
    do_update_ipa_sh()


if __name__ == "__main__":
    main()
