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
    espeak -v en --ipa -q "$text" 2>/dev/null | tr -d '\n'
}

for dir in phrases phrasebook-topics; do
    for file in "$dir"/*.txt; do
        [ -f "$file" ] || continue
        temp_file="${file}.tmp"
        while IFS='|' read -r phrase translation ipa; do
            phrase=$(echo "$phrase" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            translation=$(echo "$translation" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [[ "$phrase" == \#* || -z "$phrase" ]] && { echo "$phrase | $translation | $ipa" >> "$temp_file"; continue; }
            real_ipa=$(get_ipa "$phrase")
            echo "$phrase | $translation | [$real_ipa]" >> "$temp_file"
        done < "$file"
        mv "$temp_file" "$file"
        echo "  ✓ $file"
    done
done

echo "✓ Done."
