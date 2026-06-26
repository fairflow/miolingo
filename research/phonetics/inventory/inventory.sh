#!/bin/bash
# Empirically derive the IPA phoneme inventory espeak-ng emits for a voice,
# by phonemizing a large word list and collecting distinct segments.
ESPEAK=/opt/local/bin/espeak-ng
VOICE="$1"
WORDS="$2"
$ESPEAK -v "$VOICE" -q --ipa --sep='|' -f "$WORDS" 2>/dev/null \
  | tr ' ' '\n' | tr '|' '\n' \
  | sed 's/[ˈˌ\-]//g' \
  | grep -v '^$' | sort | uniq -c | sort -rn
