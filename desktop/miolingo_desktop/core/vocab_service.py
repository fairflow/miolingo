"""Vocabulary services that don't belong in the repository or the UI.

UI-free helpers: CSV export (string output, so it's trivially testable and the
Qt layer just writes it to a file) and IPA autofill via espeak. Translation
autofill needs an online LLM/DeepL call (deferred — see QUESTIONS.md); this
fills IPA offline and leaves translation to the user for v1.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from typing import Any

from . import config
from .phonemes import get_ipa_from_espeak

# Columns exported to CSV (and the header row), in order.
CSV_FIELDS = [
    "word",
    "display_word",
    "translation",
    "ipa",
    "language_code",
    "source_language_code",
    "source_name",
    "context_line",
    "url",
    "times_seen",
    "first_seen_at",
    "last_seen_at",
]


def rows_to_csv(rows: Sequence[dict[str, Any]]) -> str:
    """Render vocabulary rows to CSV text (header + one row per entry)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    return buf.getvalue()


def autofill_ipa(word: str, language_code: str) -> str | None:
    """Best-effort IPA for *word* via espeak. Returns None if unavailable."""
    ipa = get_ipa_from_espeak(word, language_code)
    if not ipa or ipa.startswith("["):  # bracketed = error/timeout/unavailable
        return None
    return ipa


def language_name_for_code(language_code: str) -> str | None:
    """Map a short code (pt, fr, ...) back to a LANGUAGE_CONFIG name, or None."""
    return config.MATERIAL_TO_TRAINING.get(language_code)
