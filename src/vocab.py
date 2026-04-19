"""
Personal Vocabulary Tracker — data helpers (F2).

Single-word dictionary of terms the user has encountered, per language,
with source + ±2 lines of context stored for every entry.

Callers from the UI layer pass explicit args (no streamlit imports here) so
these helpers can be integration-tested against a real MySQL instance.

Enrichment (translation + IPA) is opt-in via `enrich=True`. Both underlying
calls are cheap (translation is LLM-cached; espeak is local), but tests
disable enrichment to stay hermetic.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import app_mysql

logger = logging.getLogger(__name__)

# Trimmed when normalising a captured token — keep hyphen/apostrophe since
# many languages use them inside single words (e.g. "l'amour", "well-being").
_TRIM_PUNCT = ".,;:!?\"'“”‘’«»()[]{}—–-…"


def _normalise(word: str) -> Tuple[str, str]:
    """
    Return (display_word, lookup_key). `display_word` preserves the user's
    case; `lookup_key` is lowercased and stripped of surrounding punctuation
    for deduplication.
    """
    trimmed = word.strip()
    # Strip leading/trailing punctuation only — never inner characters.
    while trimmed and trimmed[0] in _TRIM_PUNCT:
        trimmed = trimmed[1:]
    while trimmed and trimmed[-1] in _TRIM_PUNCT:
        trimmed = trimmed[:-1]
    return trimmed, trimmed.lower()


class VocabCaptureError(ValueError):
    """Raised when the captured token is not a valid single word."""


def validate_single_word(word: str) -> Tuple[str, str]:
    """
    Enforce the single-word invariant. Returns (display_word, lookup_key).
    Raises VocabCaptureError if empty or contains whitespace.
    """
    if not word or not word.strip():
        raise VocabCaptureError("Empty word")
    display, key = _normalise(word)
    if not key:
        raise VocabCaptureError("Word is only punctuation")
    if re.search(r"\s", key):
        raise VocabCaptureError(
            "Dictionary entries are single words — "
            "use the context field to capture phrases"
        )
    if len(key) > 100:
        raise VocabCaptureError("Word too long (max 100 characters)")
    return display, key


def _enrich(
    word: str,
    language: str,
    source_language: str,
    secrets: Any,
) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort translation + IPA. Returns (translation, ipa), either may be None."""
    translation: Optional[str] = None
    ipa: Optional[str] = None
    try:
        from translation import get_translation_from_llm
        t = get_translation_from_llm(
            word,
            source_lang=language,
            target_lang=source_language,
            secrets=secrets,
            db_module=app_mysql,
        )
        if t and not t.startswith("[error"):
            translation = t
    except Exception as e:
        logger.warning("Translation enrichment failed for %r: %s", word, e)

    try:
        from config import get_language_code
        from scoring.phonemes import get_ipa_from_espeak
        code = get_language_code(language)
        i = get_ipa_from_espeak(word, code)
        if i and not i.startswith("[") and i != "[IPA unavailable]":
            ipa = i
    except Exception as e:
        logger.warning("IPA enrichment failed for %r: %s", word, e)

    return translation, ipa


def capture_vocab_entry(
    *,
    user_id: int,
    language: str,
    word: str,
    source_name: Optional[str] = None,
    context_before: str = "",
    context_line: str = "",
    context_after: str = "",
    enrich: bool = False,
    source_language: str = "English",
    secrets: Any = None,
) -> Dict[str, Any]:
    """
    Insert a vocab entry, or bump `times_seen` / `last_seen_at` if the word
    already exists for this (user, language). First encounter wins for
    source/context/translation/ipa — never overwrite non-null existing fields.

    Returns {"ok": bool, "vocab_id": int | None, "created": bool, "message": str}.
    """
    try:
        display, key = validate_single_word(word)
    except VocabCaptureError as e:
        return {"ok": False, "vocab_id": None, "created": False, "message": str(e)}

    translation: Optional[str] = None
    ipa: Optional[str] = None
    if enrich:
        translation, ipa = _enrich(display, language, source_language, secrets)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn = app_mysql.get_connection()
    cur = conn.cursor()

    # Upsert — on duplicate, bump counters and fill any NULL fields but
    # never overwrite existing non-null values.
    cur.execute(
        """
        INSERT INTO vocab_entries (
            user_id, language_code, word, display_word,
            translation, ipa, source_name,
            context_before, context_line, context_after,
            times_seen, first_seen_at, last_seen_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
        ON DUPLICATE KEY UPDATE
            times_seen = times_seen + 1,
            last_seen_at = VALUES(last_seen_at),
            translation   = COALESCE(translation, VALUES(translation)),
            ipa           = COALESCE(ipa, VALUES(ipa)),
            source_name   = COALESCE(source_name, VALUES(source_name)),
            context_before= COALESCE(NULLIF(context_before,''), VALUES(context_before)),
            context_line  = COALESCE(NULLIF(context_line,''),   VALUES(context_line)),
            context_after = COALESCE(NULLIF(context_after,''),  VALUES(context_after))
        """,
        (
            user_id, language, key, display,
            translation, ipa, source_name,
            context_before or None, context_line or None, context_after or None,
            now, now,
        ),
    )
    conn.commit()
    created = cur.rowcount == 1  # MySQL returns 1 on insert, 2 on update
    # Fetch the vocab_id (lastrowid is 0 on pure update in some drivers)
    vocab_id = cur.lastrowid
    if not vocab_id:
        cur.execute(
            "SELECT vocab_id FROM vocab_entries "
            "WHERE user_id=%s AND language_code=%s AND word=%s",
            (user_id, language, key),
        )
        row = cur.fetchone()
        vocab_id = row[0] if row else None
    cur.close()
    return {
        "ok": True,
        "vocab_id": vocab_id,
        "created": created,
        "message": "added" if created else "updated",
    }


def list_vocab(
    *,
    user_id: int,
    language: str,
    sort: str = "alpha",
    search: str = "",
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    List the user's vocabulary for a language.

    sort: 'alpha' (default, by lookup key), 'recent' (last_seen_at DESC),
          'oldest' (first_seen_at ASC).
    search: case-insensitive substring match over word OR translation.
    """
    order = {
        "alpha": "word ASC",
        "recent": "last_seen_at DESC",
        "oldest": "first_seen_at ASC",
    }.get(sort, "word ASC")

    conn = app_mysql.get_connection()
    cur = conn.cursor(dictionary=True)
    if search:
        like = f"%{search.lower()}%"
        cur.execute(
            f"""
            SELECT * FROM vocab_entries
            WHERE user_id=%s AND language_code=%s
              AND (LOWER(word) LIKE %s OR LOWER(COALESCE(translation,'')) LIKE %s)
            ORDER BY {order}
            LIMIT %s
            """,
            (user_id, language, like, like, limit),
        )
    else:
        cur.execute(
            f"""
            SELECT * FROM vocab_entries
            WHERE user_id=%s AND language_code=%s
            ORDER BY {order}
            LIMIT %s
            """,
            (user_id, language, limit),
        )
    rows = cur.fetchall()
    cur.close()
    return rows


def get_vocab_entry(*, user_id: int, vocab_id: int) -> Optional[Dict[str, Any]]:
    conn = app_mysql.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM vocab_entries WHERE vocab_id=%s AND user_id=%s",
        (vocab_id, user_id),
    )
    row = cur.fetchone()
    cur.close()
    return row


def delete_vocab_entry(*, user_id: int, vocab_id: int) -> bool:
    conn = app_mysql.get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM vocab_entries WHERE vocab_id=%s AND user_id=%s",
        (vocab_id, user_id),
    )
    conn.commit()
    affected = cur.rowcount
    cur.close()
    return affected > 0


def update_vocab_notes(*, user_id: int, vocab_id: int, notes: str) -> bool:
    conn = app_mysql.get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE vocab_entries SET notes=%s WHERE vocab_id=%s AND user_id=%s",
        (notes, vocab_id, user_id),
    )
    conn.commit()
    affected = cur.rowcount
    cur.close()
    return affected > 0


def _parse_import_line(line: str) -> Optional[Dict[str, str]]:
    """Pipe-delimited: `word | source | context`. All three required; context may be empty."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 2:
        return None
    word = parts[0]
    source = parts[1] if len(parts) >= 2 else ""
    context = parts[2] if len(parts) >= 3 else ""
    if not word:
        return None
    return {"word": word, "source": source, "context": context}


def import_from_file_contents(
    *,
    user_id: int,
    language: str,
    contents: str,
    enrich: bool = False,
    source_language: str = "English",
    secrets: Any = None,
) -> Dict[str, Any]:
    """
    Parse a pipe-delimited dictionary file and capture each valid row.
    Returns a summary dict with `added`, `updated`, `skipped_not_single`,
    `skipped_other`, and a list of skipped rows for display.
    """
    added = 0
    updated = 0
    skipped_not_single: List[str] = []
    skipped_other: List[Tuple[str, str]] = []

    for lineno, raw in enumerate(contents.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed = _parse_import_line(line)
        if not parsed:
            skipped_other.append((f"line {lineno}", "unparseable"))
            continue
        result = capture_vocab_entry(
            user_id=user_id,
            language=language,
            word=parsed["word"],
            source_name=parsed["source"] or None,
            context_line=parsed["context"],
            enrich=enrich,
            source_language=source_language,
            secrets=secrets,
        )
        if not result["ok"]:
            msg = result["message"]
            if "single" in msg:
                skipped_not_single.append(parsed["word"])
            else:
                skipped_other.append((parsed["word"], msg))
            continue
        if result["created"]:
            added += 1
        else:
            updated += 1

    return {
        "added": added,
        "updated": updated,
        "skipped_not_single": skipped_not_single,
        "skipped_other": skipped_other,
    }


def vocab_as_practice_phrases(
    *,
    user_id: int,
    language: str,
    sort: str = "alpha",
) -> List[Dict[str, Any]]:
    """
    Shape vocab entries to match the phrase-dict interface expected by the
    practice UI: {text, translation, ipa}. Used by the 'Practice from vocab'
    material source.
    """
    rows = list_vocab(user_id=user_id, language=language, sort=sort)
    return [
        {
            "text": r["display_word"],
            "translation": r.get("translation") or "",
            "ipa": r.get("ipa") or "",
        }
        for r in rows
    ]
