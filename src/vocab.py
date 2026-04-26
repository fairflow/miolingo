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
    url: Optional[str] = None,
    translation: Optional[str] = None,
    ipa: Optional[str] = None,
    enrich: bool = False,
    source_language: str = "English",
    source_language_code: Optional[str] = None,
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

    if enrich and (not translation or not ipa):
        enrich_t, enrich_i = _enrich(display, language, source_language, secrets)
        if not translation:
            translation = enrich_t
        if not ipa:
            ipa = enrich_i

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn = app_mysql.get_connection()
    cur = conn.cursor()

    # Upsert — on duplicate, bump counters and fill any NULL fields but
    # never overwrite existing non-null values.
    cur.execute(
        """
        INSERT INTO vocab_entries (
            user_id, language_code, source_language_code, word, display_word,
            translation, ipa, source_name,
            context_before, context_line, context_after,
            url, times_seen, first_seen_at, last_seen_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
        ON DUPLICATE KEY UPDATE
            times_seen = times_seen + 1,
            last_seen_at = VALUES(last_seen_at),
            translation   = COALESCE(translation, VALUES(translation)),
            ipa           = COALESCE(ipa, VALUES(ipa)),
            source_name   = COALESCE(source_name, VALUES(source_name)),
            context_before= COALESCE(NULLIF(context_before,''), VALUES(context_before)),
            context_line  = COALESCE(NULLIF(context_line,''),   VALUES(context_line)),
            context_after = COALESCE(NULLIF(context_after,''),  VALUES(context_after)),
            url           = COALESCE(NULLIF(url,''), VALUES(url))
        """,
        (
            user_id, language, source_language_code, key, display,
            translation, ipa, source_name,
            context_before or None, context_line or None, context_after or None,
            url or None, now, now,
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
    source_language_code: Optional[str] = None,
    sort: str = "alpha",
    search: str = "",
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    List the user's vocabulary for a language.

    source_language_code: optional — when provided, only rows whose
        stored ``source_language_code`` matches OR is NULL are returned
        (NULL = unspecified, treated as compatible with any source).
        When None (default), no source filter is applied.
    sort: 'alpha' (default, by lookup key), 'recent' (last_seen_at DESC),
          'oldest' (first_seen_at ASC).
    search: mini-language query — plain text still means substring on word
            OR translation. See src/vocab_search.py for the grammar.
            Unknown fields, unterminated quotes, etc. raise QueryError.
    """
    order = {
        "alpha": "word ASC",
        "recent": "last_seen_at DESC",
        "oldest": "first_seen_at ASC",
    }.get(sort, "word ASC")

    # Build optional WHERE fragment from the query mini-language.
    extra_sql = ""
    extra_params: List[Any] = []
    if search:
        import vocab_search
        clauses = vocab_search.parse_query(search)
        if clauses:
            where_sql, extra_params = vocab_search.build_where(clauses)
            if where_sql:
                extra_sql = " AND " + where_sql

    src_sql = ""
    src_params: List[Any] = []
    if source_language_code:
        src_sql = " AND (source_language_code = %s OR source_language_code IS NULL)"
        src_params = [source_language_code]

    conn = app_mysql.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
        SELECT * FROM vocab_entries
        WHERE user_id=%s AND language_code=%s
          {src_sql}
          {extra_sql}
        ORDER BY {order}
        LIMIT %s
        """,
        [user_id, language, *src_params, *extra_params, limit],
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


def list_vocab_source_breakdown(
    *, user_id: int, language: str
) -> List[Dict[str, Any]]:
    """Return per-source-pairing row counts for (user_id, language_code).

    Used by the vocab tab to explain "0 entries" when rows exist under a
    different source pairing than the user's current sidebar source.

    Returns rows like::

        [{"source_language_code": "pt", "cnt": 22},
         {"source_language_code": None, "cnt": 261}]

    Sorted by count desc. Empty list if the user has no rows for the
    language at all.
    """
    conn = app_mysql.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT source_language_code, COUNT(*) AS cnt "
        "FROM vocab_entries "
        "WHERE user_id=%s AND language_code=%s "
        "GROUP BY source_language_code "
        "ORDER BY cnt DESC",
        (user_id, language),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


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


# Fields that the post-capture edit form may modify. `word` (the lookup key)
# is intentionally excluded — changing it would require re-deduplication.
# `notes` has its own dedicated save flow. `times_seen` / `first_seen_at` /
# `last_seen_at` are capture-side counters, not user-editable.
_EDITABLE_FIELDS = (
    "display_word",
    "translation",
    "ipa",
    "source_name",
    "url",
    "context_before",
    "context_line",
    "context_after",
)


def update_vocab_entry(*, user_id: int, vocab_id: int, **fields: Any) -> bool:
    """Update a subset of editable fields on an entry owned by ``user_id``.

    - Rejects keys outside ``_EDITABLE_FIELDS`` with ``ValueError``.
    - For ``display_word``: the new value must round-trip to the same lookup
      key (``_normalise(new)[1] == row["word"]``); otherwise ``ValueError``.
      This allows casing fixes but preserves the unique (user_id, language,
      word) key.
    - Each value is normalised with ``(x or "").strip()``; an empty string
      is persisted as ``NULL``.
    - A delta against the current row is computed; if nothing changed, no
      SQL runs and ``True`` is returned.
    - Returns ``True`` if the row exists and belongs to ``user_id``;
      ``False`` otherwise.
    """
    unknown = set(fields) - set(_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown editable field(s): {sorted(unknown)}. "
            f"Allowed: {list(_EDITABLE_FIELDS)}"
        )

    row = get_vocab_entry(user_id=user_id, vocab_id=vocab_id)
    if row is None:
        return False

    # Validate display_word preserves the lookup key.
    if "display_word" in fields:
        new_display = (fields["display_word"] or "").strip()
        if not new_display:
            raise ValueError("display_word cannot be empty")
        _, new_key = _normalise(new_display)
        if new_key != row["word"]:
            raise ValueError(
                f"display_word {new_display!r} would change lookup key "
                f"from {row['word']!r} to {new_key!r}; "
                "editing the lookup key is not supported"
            )

    # Build delta: only columns whose normalised value differs from current.
    delta: Dict[str, Optional[str]] = {}
    for col, raw in fields.items():
        new_val: Optional[str] = (raw or "").strip() or None
        cur_val = row.get(col)
        cur_norm: Optional[str] = (cur_val or "").strip() or None if isinstance(cur_val, str) else cur_val
        if new_val != cur_norm:
            delta[col] = new_val

    if not delta:
        return True  # no-op; row exists and is owned.

    set_clause = ", ".join(f"{col}=%s" for col in delta)
    params = list(delta.values()) + [vocab_id, user_id]

    conn = app_mysql.get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE vocab_entries SET {set_clause} "
        "WHERE vocab_id=%s AND user_id=%s",
        params,
    )
    conn.commit()
    cur.close()
    # Row existed and was owned (checked above); a 0 rowcount from MySQL
    # just means the driver saw no byte-level change, not a failure.
    return True


def autofill_vocab_entry(
    *,
    user_id: int,
    vocab_id: int,
    language: str,
    source_language: str,
    secrets: Any,
) -> Dict[str, Dict[str, str]]:
    """Fill missing ``translation`` / ``ipa`` on an entry via ``_enrich``.

    Only fields that are currently empty are candidates; existing values are
    never overwritten. Returns ``{"filled": {field: value, ...}}`` describing
    what was written. Returns ``{"filled": {}}`` when the entry is already
    complete, when the user does not own the row, or when ``_enrich`` could
    not produce the missing field(s).
    """
    row = get_vocab_entry(user_id=user_id, vocab_id=vocab_id)
    if row is None:
        return {"filled": {}}

    need_translation = not (row.get("translation") or "").strip()
    need_ipa = not (row.get("ipa") or "").strip()
    if not (need_translation or need_ipa):
        return {"filled": {}}

    translation, ipa = _enrich(
        row["display_word"], language, source_language, secrets
    )

    to_write: Dict[str, str] = {}
    if need_translation and translation:
        to_write["translation"] = translation
    if need_ipa and ipa:
        to_write["ipa"] = ipa

    if not to_write:
        return {"filled": {}}

    update_vocab_entry(user_id=user_id, vocab_id=vocab_id, **to_write)
    return {"filled": to_write}


def _parse_import_line(line: str) -> Optional[Dict[str, str]]:
    """Pipe-delimited: `word | translation | ipa | source | url` (5 positional fields).

    Only word is required.  Use `||` to leave a field blank while keeping
    later fields in the correct position — e.g. `word || [atˈɛ] | src` sets
    ipa but leaves translation empty.  IPA may be wrapped in `[]`; brackets
    are stripped.  Trailing fields may be omitted.
    """
    parts = [p.strip() for p in line.split("|")]
    if not parts:
        return None
    word = parts[0]
    if not word:
        return None
    translation = parts[1] if len(parts) >= 2 else ""
    ipa         = parts[2] if len(parts) >= 3 else ""
    source      = parts[3] if len(parts) >= 4 else ""
    url         = parts[4] if len(parts) >= 5 else ""
    if ipa.startswith("[") and ipa.endswith("]"):
        ipa = ipa[1:-1]
    return {"word": word, "translation": translation, "ipa": ipa,
            "source": source, "url": url}


IMPORT_LINE_LIMIT = 250
"""Maximum number of words accepted per bulk upload."""


# Canonical (source, target) header regex lives in import_header so
# language-material metadata and vocab imports share one source of truth.
from import_header import HEADER_RE as _HEADER_RE  # noqa: E402


def parse_import_header(contents: str) -> Tuple[str, str]:
    """Extract the mandatory ``(source, target)`` header from an upload.

    Scans leading blank/comment-only lines until it finds a bare
    ``(src, tgt)`` tuple (optionally preceded by ``#`` and whitespace).
    The two codes are returned lowercased. The first non-comment data line
    encountered before a valid header raises ``ValueError``.

    Examples accepted:
        ``(pt, en)``           ← preferred form, first line
        ``# (pt, en)``         ← commented form
        (blank lines and other ``#`` comments may precede it)

    Rejects anything else, including a missing header — loading proceeds
    only when the caller has established which source/target pair the
    file is authored in.
    """
    for raw in contents.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _HEADER_RE.match(raw)
        if m:
            return m.group(1).lower(), m.group(2).lower()
        # First non-blank line that isn't the header and isn't a plain
        # comment → reject. Plain "# foo" comments are allowed to precede
        # the header.
        if line.startswith("#"):
            continue
        raise ValueError(
            "Upload rejected: the first non-blank line must be a "
            "(source, target) header, e.g. `(pt, en)`. Found: "
            f"{line!r}."
        )
    raise ValueError(
        "Upload rejected: no (source, target) header found. "
        "Add a line like `(pt, en)` at the top of the file."
    )


def count_import_lines(contents: str) -> int:
    """Count non-blank, non-comment lines in a pipe-delimited import file.

    The ``(source, target)`` header is counted as a comment (it starts with
    either ``(`` or ``#``) and not as a data row.
    """
    n = 0
    for raw in contents.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if _HEADER_RE.match(raw):
            continue
        n += 1
    return n


def import_from_file_contents(
    *,
    user_id: int,
    language: str,
    contents: str,
    expected_target_code: str,
    enrich: bool = False,
    source_language: str = "English",
    secrets: Any = None,
    progress_fn=None,
) -> Dict[str, Any]:
    """
    Parse a pipe-delimited dictionary file and capture each valid row.

    The file MUST begin with a ``(source, target)`` header line (e.g.
    ``(pt, en)``) — see :func:`parse_import_header`. The target code is
    checked against ``expected_target_code`` (the user's current practice
    language code); mismatch aborts the whole import with ``ValueError``
    and no rows are captured. The source code is stored on each row.

    Returns a summary dict with `added`, `updated`, `skipped_not_single`,
    `skipped_other`, and a list of skipped rows for display.

    Raises ValueError if the file exceeds IMPORT_LINE_LIMIT (250) lines,
    if the header is missing/malformed, or if the header target does not
    match ``expected_target_code``.
    progress_fn: optional callable(current, total) called after each line.
    """
    src_code, tgt_code = parse_import_header(contents)
    if tgt_code != expected_target_code.lower():
        raise ValueError(
            f"Upload rejected: header says target is {tgt_code!r} but the "
            f"current practice language is {expected_target_code!r}. "
            "Switch language (or edit the file) before importing."
        )

    n = count_import_lines(contents)
    if n > IMPORT_LINE_LIMIT:
        raise ValueError(
            f"File has {n} words — maximum is {IMPORT_LINE_LIMIT}. "
            "Split into smaller files and import separately."
        )

    added = 0
    updated = 0
    skipped_not_single: List[str] = []
    skipped_other: List[Tuple[str, str]] = []

    lines = [
        (lineno, raw)
        for lineno, raw in enumerate(contents.splitlines(), start=1)
        if raw.strip()
        and not raw.strip().startswith("#")
        and not _HEADER_RE.match(raw)
    ]
    total = len(lines)

    for done, (lineno, raw) in enumerate(lines, start=1):
        parsed = _parse_import_line(raw.strip())
        if not parsed:
            skipped_other.append((f"line {lineno}", "unparseable"))
        else:
            result = capture_vocab_entry(
                user_id=user_id,
                language=language,
                word=parsed["word"],
                source_name=parsed["source"] or None,
                url=parsed.get("url") or None,
                translation=parsed.get("translation") or None,
                ipa=parsed.get("ipa") or None,
                enrich=enrich,
                source_language=source_language,
                source_language_code=src_code,
                secrets=secrets,
            )
            if not result["ok"]:
                msg = result["message"]
                if "single" in msg:
                    skipped_not_single.append(parsed["word"])
                else:
                    skipped_other.append((parsed["word"], msg))
            elif result["created"]:
                added += 1
            else:
                updated += 1

        if progress_fn is not None:
            progress_fn(done, total)

    return {
        "added": added,
        "updated": updated,
        "skipped_not_single": skipped_not_single,
        "skipped_other": skipped_other,
        "header_src_code": src_code,
        "header_tgt_code": tgt_code,
    }


def vocab_as_practice_phrases(
    *,
    user_id: int,
    language: str,
    source_language_code: Optional[str] = None,
    sort: str = "alpha",
    search: str = "",
) -> List[Dict[str, Any]]:
    """
    Shape vocab entries to match the phrase-dict interface expected by the
    practice UI: {text, translation, ipa}. Used by the 'Practice from vocab'
    material source.

    source_language_code: optional — forwarded to :func:`list_vocab` so
        practice from vocabulary respects the current session source.
    search: optional mini-language query to practise a filtered subset.
            Same grammar as list_vocab's search parameter. Empty string
            (default) returns the full vocabulary.
    """
    rows = list_vocab(
        user_id=user_id,
        language=language,
        source_language_code=source_language_code,
        sort=sort,
        search=search,
    )
    return [
        {
            "text": r["display_word"],
            "translation": r.get("translation") or "",
            "ipa": r.get("ipa") or "",
        }
        for r in rows
    ]
