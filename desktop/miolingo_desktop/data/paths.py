"""Resolve the on-disk location of the local SQLite database.

The DB lives in the macOS app-support directory by default
(``~/Library/Application Support/Miolingo/miolingo.db``). Tests and packaging
override the location via ``MIOLINGO_DB_PATH`` (or by passing an explicit path
to the repositories), so nothing here is hard-coded into call sites.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Miolingo"
DB_FILENAME = "miolingo.db"


def app_support_dir() -> Path:
    """Return the per-user application-support directory for Miolingo.

    macOS: ``~/Library/Application Support/Miolingo``. Other platforms get a
    sensible fallback (XDG-ish) so the code stays cross-platform-clean even
    though v1 ships macOS only.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":  # pragma: no cover - Windows is a non-goal for v1
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:  # pragma: no cover - Linux is a non-goal for v1
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME


def default_db_path() -> Path:
    """Resolve the DB path: ``$MIOLINGO_DB_PATH`` if set, else app-support dir."""
    env = os.environ.get("MIOLINGO_DB_PATH")
    if env:
        return Path(env)
    return app_support_dir() / DB_FILENAME
