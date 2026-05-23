"""Typed repository classes over the SQLite tables.

Each repository wraps a :class:`~miolingo_desktop.data.database.Database` and
exposes plain methods returning plain dicts/values — no Qt, no Streamlit. Data
shapes mirror the source app's ``app_mysql`` / ``vocab`` so the ported core
logic fits without translation.

Sync-ready invariants enforced here:
- every insert gets a UUID ``id`` and ``created_at``/``updated_at`` timestamps;
- deletes are **soft** (set ``deleted_at``); reads exclude soft-deleted rows
  unless ``include_deleted=True``;
- ``updated_at`` is refreshed on every mutation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from typing import Any

from .database import Database, utcnow_iso


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsRepository:
    """Key/value app settings persistence (mirrors config.load/save_settings)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str, default: Any = None) -> Any:
        row = self._db.connection.execute(
            "SELECT value FROM settings WHERE key = ? AND deleted_at IS NULL",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return json.loads(row["value"]) if row["value"] is not None else None

    def set(self, key: str, value: Any) -> None:
        now = utcnow_iso()
        encoded = json.dumps(value)
        conn = self._db.connection
        with conn:
            existing = conn.execute(
                "SELECT id FROM settings WHERE key = ?", (key,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO settings (id, key, value, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (_new_id(), key, encoded, now, now),
                )
            else:
                conn.execute(
                    "UPDATE settings SET value = ?, updated_at = ?, deleted_at = NULL "
                    "WHERE key = ?",
                    (encoded, now, key),
                )

    def get_all(self) -> dict[str, Any]:
        rows = self._db.connection.execute(
            "SELECT key, value FROM settings WHERE deleted_at IS NULL"
        ).fetchall()
        return {
            r["key"]: (json.loads(r["value"]) if r["value"] is not None else None)
            for r in rows
        }

    def update_many(self, settings: dict[str, Any]) -> None:
        for key, value in settings.items():
            self.set(key, value)


# ---------------------------------------------------------------------------
# Practice attempts (history)
# ---------------------------------------------------------------------------


class PracticeRepository:
    """Practice attempt history (mirrors app_mysql.save_practice/get_user_progress)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save_attempt(
        self,
        *,
        language_code: str,
        target_phrase: str,
        recognized_phrase: str | None,
        similarity_score: float,
        perfect_match: bool,
        target_phonemes: str = "",
        user_phonemes: str = "",
    ) -> str:
        """Insert a practice attempt and return its new id."""
        now = utcnow_iso()
        attempt_id = _new_id()
        conn = self._db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO practice_attempts (
                    id, language_code, target_phrase, recognized_phrase,
                    similarity_score, perfect_match, target_phonemes, user_phonemes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    language_code,
                    target_phrase,
                    recognized_phrase,
                    float(similarity_score),
                    1 if perfect_match else 0,
                    target_phonemes,
                    user_phonemes,
                    now,
                    now,
                ),
            )
        return attempt_id

    def save_from_result(self, language_code: str, result: dict[str, Any]) -> str:
        """Persist a ``practice_word_from_audio`` result dict.

        Maps the core pipeline's ``similarity`` (0..1) to a 0..100 score to match
        the source app's stored convention.
        """
        return self.save_attempt(
            language_code=language_code,
            target_phrase=result.get("target", ""),
            recognized_phrase=result.get("recognized", ""),
            similarity_score=round(float(result.get("similarity", 0.0)) * 100, 2),
            perfect_match=bool(result.get("exact_match", False)),
            target_phonemes=result.get("correct_phonemes_normalized", "") or "",
            user_phonemes=result.get("user_phonemes_normalized", "") or "",
        )

    def list_history(
        self,
        *,
        language_code: str | None = None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if not include_deleted:
            clauses.append("deleted_at IS NULL")
        if language_code is not None:
            clauses.append("language_code = ?")
            params.append(language_code)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self._db.connection.execute(
            f"SELECT * FROM practice_attempts{where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def soft_delete(self, attempt_id: str) -> None:
        now = utcnow_iso()
        conn = self._db.connection
        with conn:
            conn.execute(
                "UPDATE practice_attempts SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, attempt_id),
            )


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class VocabularyRepository:
    """Per-language vocabulary tracker (mirrors src/vocab.py shapes)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def capture(
        self,
        *,
        language_code: str,
        word: str,
        display_word: str | None = None,
        source_language_code: str | None = None,
        translation: str | None = None,
        ipa: str | None = None,
        source_name: str | None = None,
        context_before: str | None = None,
        context_line: str | None = None,
        context_after: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Insert a word, or bump ``times_seen`` if it already exists.

        First encounter wins for translation/ipa/source/context — existing
        non-null fields are never overwritten (matches the source upsert).
        Returns ``{"id", "created"}``.
        """
        now = utcnow_iso()
        conn = self._db.connection
        with conn:
            existing = conn.execute(
                "SELECT * FROM vocabulary WHERE language_code = ? AND word = ?",
                (language_code, word),
            ).fetchone()

            if existing is None:
                vocab_id = _new_id()
                conn.execute(
                    """
                    INSERT INTO vocabulary (
                        id, language_code, source_language_code, word, display_word,
                        translation, ipa, source_name,
                        context_before, context_line, context_after, url,
                        times_seen, first_seen_at, last_seen_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        vocab_id, language_code, source_language_code, word,
                        display_word or word, translation, ipa, source_name,
                        context_before, context_line, context_after, url,
                        now, now, now, now,
                    ),
                )
                return {"id": vocab_id, "created": True}

            # Resurrect a soft-deleted row on re-capture; bump counters; fill NULLs.
            conn.execute(
                """
                UPDATE vocabulary SET
                    times_seen = times_seen + 1,
                    last_seen_at = ?,
                    updated_at = ?,
                    deleted_at = NULL,
                    translation    = COALESCE(translation, ?),
                    ipa            = COALESCE(ipa, ?),
                    source_name    = COALESCE(source_name, ?),
                    context_before = COALESCE(NULLIF(context_before, ''), ?),
                    context_line   = COALESCE(NULLIF(context_line, ''), ?),
                    context_after  = COALESCE(NULLIF(context_after, ''), ?),
                    url            = COALESCE(NULLIF(url, ''), ?)
                WHERE id = ?
                """,
                (
                    now, now, translation, ipa, source_name,
                    context_before, context_line, context_after, url,
                    existing["id"],
                ),
            )
            return {"id": existing["id"], "created": False}

    def get(self, vocab_id: str) -> dict[str, Any] | None:
        row = self._db.connection.execute(
            "SELECT * FROM vocabulary WHERE id = ?", (vocab_id,)
        ).fetchone()
        return dict(row) if row else None

    def update(self, vocab_id: str, **fields: Any) -> None:
        """Update editable fields (translation, ipa, context, etc.)."""
        allowed = {
            "display_word", "translation", "ipa", "source_name",
            "context_before", "context_line", "context_after", "url",
            "source_language_code",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        now = utcnow_iso()
        assignments = ", ".join(f"{k} = ?" for k in sets)
        params = [*sets.values(), now, vocab_id]
        conn = self._db.connection
        with conn:
            conn.execute(
                f"UPDATE vocabulary SET {assignments}, updated_at = ? WHERE id = ?",
                params,
            )

    def list(
        self,
        *,
        language_code: str,
        sort: str = "alpha",
        search: str = "",
        include_deleted: bool = False,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        order = {
            "alpha": "word ASC",
            "recent": "last_seen_at DESC",
            "oldest": "first_seen_at ASC",
        }.get(sort, "word ASC")

        clauses = ["language_code = ?"]
        params: list[Any] = [language_code]
        if not include_deleted:
            clauses.append("deleted_at IS NULL")
        if search:
            clauses.append("(word LIKE ? OR translation LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        params.append(limit)

        rows = self._db.connection.execute(
            f"SELECT * FROM vocabulary WHERE {' AND '.join(clauses)} "
            f"ORDER BY {order} LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def soft_delete(self, vocab_id: str) -> None:
        now = utcnow_iso()
        conn = self._db.connection
        with conn:
            conn.execute(
                "UPDATE vocabulary SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, vocab_id),
            )

    def export_csv_rows(self, *, language_code: str) -> Iterable[dict[str, Any]]:
        """Yield rows suitable for CSV export (live rows only)."""
        yield from self.list(language_code=language_code, limit=100000)
