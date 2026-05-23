"""Versioned SQLite schema migrations.

A deliberately tiny migration runner keyed on SQLite's ``PRAGMA user_version``
(chosen over alembic/yoyo to avoid a heavy dependency for a single local file —
see DECISIONS.md). Each migration is an ``(version, sql)`` pair applied in order
inside a transaction; ``user_version`` is bumped as each succeeds, so
``apply_migrations`` is idempotent and safe to run on every launch.

Schema design (sync-ready, per SPEC §6 / DECISIONS.md):
- **UUID text primary keys** (``id``) so rows merge across devices without
  autoincrement collisions.
- ``created_at`` / ``updated_at`` ISO-8601 UTC timestamps on every table.
- ``deleted_at`` soft-delete (NULL = live); reads filter it out by default.
- A nullable ``user_id`` column anticipates the future batch sync to Matthew's
  remote DB (v1 leaves it NULL — single local user, no auth).
"""

from __future__ import annotations

import sqlite3

# Each entry: (target_user_version, SQL executed to reach it).
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS settings (
            id          TEXT PRIMARY KEY,
            user_id     TEXT,
            key         TEXT NOT NULL UNIQUE,
            value       TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            deleted_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS practice_attempts (
            id                TEXT PRIMARY KEY,
            user_id           TEXT,
            language_code     TEXT NOT NULL,
            target_phrase     TEXT NOT NULL,
            recognized_phrase TEXT,
            similarity_score  REAL NOT NULL,
            perfect_match     INTEGER NOT NULL DEFAULT 0,
            target_phonemes   TEXT,
            user_phonemes     TEXT,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            deleted_at        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_attempts_lang_created
            ON practice_attempts (language_code, created_at);

        CREATE TABLE IF NOT EXISTS vocabulary (
            id                   TEXT PRIMARY KEY,
            user_id              TEXT,
            language_code        TEXT NOT NULL,
            source_language_code TEXT,
            word                 TEXT NOT NULL,
            display_word         TEXT,
            translation          TEXT,
            ipa                  TEXT,
            source_name          TEXT,
            context_before       TEXT,
            context_line         TEXT,
            context_after        TEXT,
            url                  TEXT,
            times_seen           INTEGER NOT NULL DEFAULT 1,
            first_seen_at        TEXT,
            last_seen_at         TEXT,
            created_at           TEXT NOT NULL,
            updated_at           TEXT NOT NULL,
            deleted_at           TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_unique_word
            ON vocabulary (language_code, word);
        """,
    ),
]


def current_version(conn: sqlite3.Connection) -> int:
    """Return the database's current ``user_version``."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply any pending migrations in order. Returns the resulting version."""
    version = current_version(conn)
    for target, sql in MIGRATIONS:
        if target <= version:
            continue
        # executescript manages its own transaction (it COMMITs any pending one
        # first), so we don't wrap it in ``with conn:``. We bump user_version in
        # the same script-driven sequence and commit explicitly afterwards.
        try:
            conn.executescript(sql)
            conn.execute(f"PRAGMA user_version = {target}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        version = target
    return version
