"""Local SQLite storage layer + migrations.

Public API:
- ``Database`` — opens the SQLite file, applies migrations, hands out a
  connection. Path resolves via ``MIOLINGO_DB_PATH`` or the macOS app-support
  directory (``paths.default_db_path``).
- ``SettingsRepository`` / ``PracticeRepository`` / ``VocabularyRepository`` —
  typed CRUD over the sync-ready tables (UUID PKs, timestamps, soft-delete).
"""

from .database import Database, utcnow_iso
from .paths import app_support_dir, default_db_path
from .repositories import (
    PracticeRepository,
    SettingsRepository,
    VocabularyRepository,
)

__all__ = [
    "Database",
    "utcnow_iso",
    "app_support_dir",
    "default_db_path",
    "SettingsRepository",
    "PracticeRepository",
    "VocabularyRepository",
]
