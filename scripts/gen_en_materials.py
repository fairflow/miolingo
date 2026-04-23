#!/usr/bin/env python3
"""Generate language_materials/en/ by inverting fr/ phrase files.

The fr/ files have the format:
    French phrase | English translation | [fr_ipa]

Inverting them for the en/ folder yields:
    English phrase | French phrase | [en_ipa]

The language pair header written to each output file is `(fr, en)`:
  - source language (translation column): French (fr)
  - target language (word column): English (en)

English IPA is generated via `espeak -v en --ipa`.

Files generated:
  phrases/phrases-001.txt … phrases-005.txt
  phrasebook-topics/*.txt
  story-phrases.txt
  phrasebook_complete.json
  metadata.json
  update_ipa.sh

Note: en/words/ was generated separately from pt/words by gen_en_words.py
(source language there is Portuguese). This script does NOT touch en/words/.
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
    """Get English IPA for *text* via espeak.  Collapses multi-line output."""
    if text in _ipa_cache:
        return _ipa_cache[text]
    try:
        res = subprocess.run(
            ["espeak", "-v", "en", "--ipa", "-q", text],
            capture_output=True, text=True, timeout=10,
        )
        ipa = " ".join(res.stdout.split())  # espeak can split on mid-phrase newlines
    except Exception:
        ipa = ""
    _ipa_cache[text] = ipa
    return ipa


# ---------------------------------------------------------------------------
# Line-level helpers
# ---------------------------------------------------------------------------

def _is_blank_or_comment(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def _parse_triple(line: str) -> tuple[str, str, str] | None:
    """Parse `french | english | [ipa]`  →  (french, english, ipa) or None."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 2 or not parts[0]:
        return None
    french = parts[0]
    english = parts[1] if len(parts) > 1 else ""
    raw_ipa = parts[2].strip() if len(parts) > 2 else ""
    # strip surrounding [ ]
    if raw_ipa.startswith("[") and raw_ipa.endswith("]"):
        raw_ipa = raw_ipa[1:-1]
    return french, english, raw_ipa


def invert_phrase_line(line: str) -> str:
    """Flip fr↔en columns and regenerate English IPA.

    Blank / comment lines pass through unchanged.
    Lines that don't parse as triples pass through unchanged.
    """
    if _is_blank_or_comment(line):
        return line
    triple = _parse_triple(line)
    if triple is None:
        return line
    french, english, _old_ipa = triple
    if not english:
        # No English side — keep French but mark translation empty
        new_ipa = en_ipa(french)
        return f"{french} |  | [{new_ipa}]" if new_ipa else f"{french} | "
    new_ipa = en_ipa(english)
    ipa_col = f" | [{new_ipa}]" if new_ipa else ""
    return f"{english} | {french}{ipa_col}"


def _adapt_comment(line: str) -> str:
    """Rewrite obvious French-specific markers in comment lines."""
    return (
        line
        .replace("French Phrasebook", "English Phrasebook")
        .replace("French phrases", "English phrases")
        .replace("French words", "English words")
        .replace("fr-fr", "en")
        .replace("espeak-ng -v fr", "espeak -v en")
        .replace("french | english", "english | french")
        .replace("Format: word | translation", "Format: english | french")
    )


# ---------------------------------------------------------------------------
# File processors
# ---------------------------------------------------------------------------

HEADER_LINE = "(fr, en)"


def _convert_phrase_file(src: Path, dst: Path) -> int:
    """Invert a phrase file; return number of data lines written."""
    lines = src.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    data_count = 0
    header_written = False

    for line in lines:
        if _is_blank_or_comment(line):
            out.append(_adapt_comment(line))
            # Insert language-pair header after the last leading comment block
        else:
            if not header_written:
                out.append(HEADER_LINE)
                header_written = True
            inverted = invert_phrase_line(line)
            out.append(inverted)
            data_count += 1

    if not header_written:
        # File was all comments / empty — prepend header
        out.insert(0, HEADER_LINE)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return data_count


def convert_phrases_dir() -> None:
    src_dir = FR / "phrases"
    dst_dir = EN / "phrases"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_file in sorted(src_dir.glob("phrases-*.txt")):
        dst_file = dst_dir / src_file.name
        n = _convert_phrase_file(src_file, dst_file)
        print(f"  phrases/{src_file.name}: {n} phrases")


def convert_phrasebook_topics() -> None:
    src_dir = FR / "phrasebook-topics"
    dst_dir = EN / "phrasebook-topics"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_file in sorted(src_dir.glob("*.txt")):
        dst_file = dst_dir / src_file.name
        n = _convert_phrase_file(src_file, dst_file)
        print(f"  phrasebook-topics/{src_file.name}: {n} phrases")


def convert_story_phrases() -> None:
    src = FR / "story-phrases.txt"
    dst = EN / "story-phrases.txt"
    n = _convert_phrase_file(src, dst)
    print(f"  story-phrases.txt: {n} phrases")


def convert_phrasebook_complete() -> None:
    src = FR / "phrasebook_complete.json"
    data = json.loads(src.read_text(encoding="utf-8"))

    # Flip metadata
    if "metadata" in data:
        m = data["metadata"]
        m["source"] = m.get("source", "").replace("French", "English")
        m["language"] = "en"

    # Flip phrases list
    if "phrases" in data:
        new_phrases = []
        for p in data["phrases"]:
            french = p.get("phrase", p.get("text", ""))
            english = p.get("translation", "")
            if not english:
                new_phrases.append(p)
                continue
            new_p = dict(p)
            new_p["phrase"] = english
            new_p["text"] = english
            new_p["translation"] = french
            new_p["ipa"] = en_ipa(english)
            new_phrases.append(new_p)
        data["phrases"] = new_phrases

    out = EN / "phrasebook_complete.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  phrasebook_complete.json: {len(data.get('phrases', []))} phrases")


def write_metadata() -> None:
    fr_meta = json.loads((FR / "metadata.json").read_text(encoding="utf-8"))
    # Adapt for English
    fr_meta["language_code"] = "en"
    fr_meta["language_name"] = "English"
    fr_meta["ipa_source"] = "Generated with espeak (British English)"
    fr_meta["generated_date"] = "2026-04-23"
    fr_meta["source_language"] = "fr"
    fr_meta["source_language_name"] = "French"

    out = EN / "metadata.json"
    out.write_text(json.dumps(fr_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  metadata.json")


def write_update_ipa_sh() -> None:
    script = """\
#!/bin/bash
# Update IPA transcriptions for English using espeak
# Usage: bash update_ipa.sh  (run from language_materials/en/)

if ! command -v espeak &> /dev/null; then
    echo "Error: espeak not found."
    exit 1
fi

echo "Updating IPA transcriptions for English phrases..."

get_ipa() {
    local text="$1"
    espeak -v en --ipa -q "$text" 2>/dev/null | tr -d '\\n'
}

for dir in phrases phrasebook-topics; do
    for file in "$dir"/*.txt; do
        [ -f "$file" ] || continue
        temp_file="${file}.tmp"
        while IFS='|' read -r phrase translation ipa; do
            phrase=$(echo "$phrase" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            translation=$(echo "$translation" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [[ "$phrase" == \\#* || -z "$phrase" ]] && { echo "$phrase | $translation | $ipa" >> "$temp_file"; continue; }
            real_ipa=$(get_ipa "$phrase")
            echo "$phrase | $translation | [$real_ipa]" >> "$temp_file"
        done < "$file"
        mv "$temp_file" "$file"
        echo "  ✓ $file"
    done
done

echo "✓ Done."
"""
    out = EN / "update_ipa.sh"
    out.write_text(script, encoding="utf-8")
    out.chmod(0o755)
    print("  update_ipa.sh")


# ---------------------------------------------------------------------------
# words/ headers
# ---------------------------------------------------------------------------

def add_word_file_headers() -> None:
    """Add (pt, en) language-pair header to en/words files that lack one."""
    HEADER = "(pt, en)"
    words_dir = EN / "words"
    for txt in sorted(words_dir.glob("*.txt")):
        content = txt.read_text(encoding="utf-8")
        # Check if the header tuple is already present on any line
        already = any(
            re.match(r"^\s*#?\s*\(\s*pt\s*,\s*en\s*\)\s*$", ln.strip(), re.IGNORECASE)
            for ln in content.splitlines()
        )
        if already:
            print(f"  words/{txt.name}: header already present")
            continue
        # Insert header after the final leading comment / blank block
        lines = content.splitlines()
        insert_at = 0
        for i, ln in enumerate(lines):
            if ln.strip().startswith("#") or not ln.strip():
                insert_at = i + 1
            else:
                break
        lines.insert(insert_at, HEADER)
        txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  words/{txt.name}: added (pt, en) header")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Generating language_materials/en/ from fr/ ...")

    print("\n[phrases]")
    convert_phrases_dir()

    print("\n[phrasebook-topics]")
    convert_phrasebook_topics()

    print("\n[story-phrases]")
    convert_story_phrases()

    print("\n[phrasebook_complete.json]")
    convert_phrasebook_complete()

    print("\n[metadata + update_ipa.sh]")
    write_metadata()
    write_update_ipa_sh()

    print("\n[words headers]")
    add_word_file_headers()

    print("\nDone.")


if __name__ == "__main__":
    main()
