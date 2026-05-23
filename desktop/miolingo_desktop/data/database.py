"""SQLite connection management + first-run initialisation.

Opens (creating parent dirs as needed) the local SQLite database, applies
migrations, and hands out connections with sensible pragmas:
- ``row_factory = sqlite3.Row`` so repositories return dict-like rows.
- WAL journal mode for better concurrent read/write (UI thread reads while a
  worker writes).
- ``foreign_keys = ON`` for integrity.

A single ``Database`` instance is shared by the repositories. It is intentionally
thin — no ORM (see DECISIONS.md).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .migrations import apply_migrations
from .paths import default_db_path


def utcnow_iso() -> str:
    """Current UTC time as an ISO-8601 string (the timestamp format used in the DB)."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class Database:
    """Owns the SQLite connection and runs migrations on open."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if str(self.path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        apply_migrations(self._conn)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
