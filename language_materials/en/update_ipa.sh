#!/bin/bash
# Regenerate IPA for every English phrase/word file under this directory
# using espeak. Run from this directory.
set -euo pipefail

if ! command -v espeak >/dev/null 2>&1; then
    echo "Error: espeak not found." >&2
    exit 1
fi

ipa() { espeak -v en --ipa -q "$1" 2>/dev/null | tr -d '\n'; }

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
