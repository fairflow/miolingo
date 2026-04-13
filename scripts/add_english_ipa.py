#!/Users/matthew/Software/working/miolingo/venv/bin/python3
"""
add_english_ipa.py — Add missing English IPA to unified language material JSON files.

For every phrase in every unified JSON file that has text["en"] but no ipa["en"],
calls espeak to generate the IPA and writes it back in the same [brackets] format
used by all other languages.

Usage:
    python scripts/add_english_ipa.py [--dry-run] [--dir PATH]

Options:
    --dry-run   Print what would be changed without writing files
    --dir PATH  Root directory to search (default: language_materials/unified)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ESPEAK_VOICE = "en-gb"   # British English; matches Google Cloud TTS default in config.py
ESPEAK_CMD   = "espeak"  # local binary name (see feedback_espeak.md)


def get_ipa(text: str) -> str | None:
    """Call espeak and return raw IPA string, or None on failure."""
    try:
        result = subprocess.run(
            [ESPEAK_CMD, "-v", ESPEAK_VOICE, "--ipa", "-q", text],
            capture_output=True, text=True, timeout=5
        )
        raw = result.stdout.strip()
        # espeak may produce multiple lines for longer phrases — join them
        raw = " ".join(line.strip() for line in raw.splitlines() if line.strip())
        return raw if raw else None
    except Exception as e:
        print(f"  ⚠️  espeak error for {text!r}: {e}", file=sys.stderr)
        return None


def add_ipa_brackets(raw: str) -> str:
    """Wrap raw espeak IPA in square brackets to match JSON format."""
    return f"[{raw}]"


def process_file(path: Path, dry_run: bool) -> tuple[int, int]:
    """
    Process a single JSON file.
    Returns (phrases_checked, phrases_updated).
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    phrases = data.get("phrases", [])
    if not phrases:
        return 0, 0

    updated = 0
    for phrase in phrases:
        text_en = phrase.get("text", {}).get("en")
        if not text_en:
            continue  # no English text, skip

        ipa_block = phrase.setdefault("ipa", {})
        if "en" in ipa_block:
            continue  # already has English IPA

        raw = get_ipa(text_en)
        if raw is None:
            print(f"  ✗ Could not generate IPA for: {text_en!r}")
            continue

        bracketed = add_ipa_brackets(raw)
        if dry_run:
            print(f"  [dry-run] {text_en!r}  →  {bracketed}")
        else:
            ipa_block["en"] = bracketed
        updated += 1

    if updated and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"  ✓ wrote {updated} IPA entr{'y' if updated == 1 else 'ies'}")

    return len(phrases), updated


def main():
    parser = argparse.ArgumentParser(description="Add English IPA to unified JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument(
        "--dir",
        default="language_materials/unified",
        help="Root directory to search (default: language_materials/unified)",
    )
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        sys.exit(f"Directory not found: {root}")

    json_files = sorted(root.rglob("*.json"))
    if not json_files:
        sys.exit(f"No JSON files found under {root}")

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Processing {len(json_files)} files in {root}/\n")

    total_phrases = total_updated = 0
    for path in json_files:
        rel = path.relative_to(root)
        print(f"📄 {rel}")
        checked, updated = process_file(path, args.dry_run)
        if updated == 0:
            print(f"  — no changes ({checked} phrases already complete)")
        total_phrases += checked
        total_updated += updated

    print(f"\n{'Would update' if args.dry_run else 'Updated'} {total_updated} phrase(s) across {len(json_files)} file(s).")


if __name__ == "__main__":
    main()
