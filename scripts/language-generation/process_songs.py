#!/usr/bin/env python3
"""
Process song.txt files to generate cleaned JSON files with IPA transcriptions.

This script:
1. Reads all `song.txt` files in a specified directory.
2. Cleans and filters the text to remove nonsense words and invalid lines.
3. Uses `espeak` to generate IPA transcriptions for Portuguese phrases.
4. Saves the results in JSON format.

Usage:
    python3 process_songs.py --input-dir /path/to/songs --output-dir /path/to/output
"""

import os
import re
import json
import subprocess
from pathlib import Path
import argparse

def clean_text(text):
    """Clean and filter text to remove nonsense words and invalid lines."""
    # Example cleaning rules (customize as needed):
    text = text.strip()
    if not text or len(text.split()) < 2:  # Remove very short lines
        return None
    if any(char.isdigit() for char in text):  # Remove lines with numbers
        return None
    return text

def get_ipa(text, lang="pt", espeak_cmd="espeak"):
    """Get IPA transcription using espeak."""
    try:
        result = subprocess.run(
            [espeak_cmd, "-v", lang, "--ipa", "-q", text],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ipa = result.stdout.strip()
            return ' '.join(ipa.split())  # Normalize whitespace
        else:
            print(f"⚠️ eSpeak error for '{text}': {result.stderr}")
            return None
    except Exception as e:
        print(f"⚠️ eSpeak error for '{text}': {e}")
        return None

def process_file(file_path, output_dir, espeak_cmd="espeak"):
    """Process a single song.txt file."""
    output_data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            cleaned = clean_text(line)
            if not cleaned:
                continue

            ipa = get_ipa(cleaned, espeak_cmd=espeak_cmd)

            if ipa:
                output_data.append({
                    "source": cleaned,
                    "ipa": ipa
                })

    # Save to JSON
    output_file = output_dir / f"{file_path.stem}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"✅ Processed {file_path} → {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Process song.txt files to generate JSON files.")
    parser.add_argument("--input-dir", required=True, help="Directory containing song.txt files.")
    parser.add_argument("--output-dir", required=True, help="Directory to save JSON output files.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"❌ Input directory does not exist: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    espeak_cmd = "espeak"
    print(f"🔧 Using eSpeak command: {espeak_cmd}")

    # Process all song.txt files
    for file_path in input_dir.glob("*.txt"):
        process_file(file_path, output_dir, espeak_cmd=espeak_cmd)

    print("✅ All files processed.")

if __name__ == "__main__":
    main()