"""Migration runner for the admin app.

Lists ``.sql`` files in ``scripts/``, splits them into statements, can
preview (dry-run) or apply them to local, remote, or both. Every successful
apply inserts an audit row into ``schema_migrations`` on the affected DB.

The audit table itself is auto-created on first use of this module — its
DDL is in ``scripts/create_schema_migrations_table.sql`` and is replayed
here lazily so admins don't have to bootstrap it manually.
"""
from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
import streamlit as st

import app_mysql
import admin_db_health  # for connection helpers


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


# ----------------------------------------------------------------------------
# SQL file discovery + parsing
# ----------------------------------------------------------------------------

def list_sql_files() -> List[Path]:
    """Return ``.sql`` files in the ``scripts/`` tree (recursively),
    sorted by name. Skips anything under ``scripts/sql_archive/``."""
    if not SCRIPTS_DIR.is_dir():
        return []
    files: List[Path] = []
    for p in SCRIPTS_DIR.rglob("*.sql"):
        if "sql_archive" in p.parts:
            continue
        files.append(p)
    files.sort(key=lambda p: p.relative_to(SCRIPTS_DIR).as_posix())
    return files


def split_statements(sql: str) -> List[str]:
    """Strip ``--`` line comments, then split on bare ``;`` terminators.
    Naive for string-literal semicolons — adequate for hand-written
    migrations. Returns trimmed non-empty statements."""
    cleaned_lines = [
        ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")
    ]
    cleaned = "\n".join(cleaned_lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------
# Audit table bootstrap + queries
# ----------------------------------------------------------------------------

_BOOTSTRAP_SQL_PATH = SCRIPTS_DIR / "create_schema_migrations_table.sql"


def _ensure_audit_table(conn) -> None:
    """Idempotently create ``schema_migrations`` on the target connection."""
    if not _BOOTSTRAP_SQL_PATH.exists():
        return
    sql = _BOOTSTRAP_SQL_PATH.read_text()
    cursor = conn.cursor()
    for stmt in split_statements(sql):
        cursor.execute(stmt)
    conn.commit()
    cursor.close()


def _record_audit(
    conn,
    *,
    filename: str,
    checksum: str,
    target: str,
    applied_by: str,
    notes: Optional[str] = None,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO schema_migrations (filename, checksum, target, applied_by, notes)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE applied_at = CURRENT_TIMESTAMP, applied_by = VALUES(applied_by)
        """,
        (filename, checksum, target, applied_by, notes),
    )
    conn.commit()
    cursor.close()


def applied_history(target: str = "remote", limit: int = 50) -> List[Dict[str, Any]]:
    """Return the recent migration history from ``schema_migrations`` on
    the named target. Empty list if the table doesn't exist yet."""
    if target == "local":
        if not admin_db_health.local_enabled():
            return []
        try:
            conn = admin_db_health._local_connect()
        except Exception:
            return []
        try:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT filename, checksum, target, applied_at, applied_by, notes "
                    "FROM schema_migrations ORDER BY applied_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
            except mysql.connector.Error:
                rows = []
            cursor.close()
        finally:
            conn.close()
        return rows

    # remote
    rows: List[Dict[str, Any]] = []
    try:
        with admin_db_health._remote_connect() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT filename, checksum, target, applied_at, applied_by, notes "
                    "FROM schema_migrations ORDER BY applied_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
            except mysql.connector.Error:
                rows = []
            cursor.close()
    except Exception:
        rows = []
    return rows


# ----------------------------------------------------------------------------
# Apply
# ----------------------------------------------------------------------------

@contextmanager
def _open_target(target: str):
    if target == "local":
        if not admin_db_health.local_enabled():
            raise RuntimeError(
                "Local DB is disabled in secrets.toml — cannot apply to local."
            )
        conn = admin_db_health._local_connect()
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass
    elif target == "remote":
        with admin_db_health._remote_connect() as conn:
            yield conn
    else:
        raise ValueError(f"Unknown target {target!r}")


def apply_migration(
    sql_path: Path,
    *,
    target: str,
    applied_by: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply every statement in ``sql_path`` to ``target`` (one of
    ``"local"`` or ``"remote"``), record audit row, return summary.

    On any failure the parent transaction is rolled back; subsequent
    statements are not attempted. Audit row is only written on success.
    """
    if target not in ("local", "remote"):
        raise ValueError(f"target must be 'local' or 'remote', got {target!r}")

    statements = split_statements(sql_path.read_text())
    if not statements:
        return {"target": target, "ok": False, "error": "no statements", "count": 0}

    with _open_target(target) as conn:
        _ensure_audit_table(conn)
        cursor = conn.cursor()
        try:
            for stmt in statements:
                cursor.execute(stmt)
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            cursor.close()
            return {
                "target": target,
                "ok": False,
                "error": str(e),
                "count": 0,
            }
        cursor.close()

        _record_audit(
            conn,
            filename=sql_path.relative_to(SCRIPTS_DIR.parent).as_posix(),
            checksum=file_checksum(sql_path),
            target=target,
            applied_by=applied_by,
            notes=notes,
        )

    return {
        "target": target,
        "ok": True,
        "count": len(statements),
    }


def already_applied(sql_path: Path, target: str) -> bool:
    """True if a row in ``schema_migrations`` matches this file+checksum
    on the named target. Used to grey-out the Apply button."""
    cs = file_checksum(sql_path)
    fn = sql_path.relative_to(SCRIPTS_DIR.parent).as_posix()
    rows = applied_history(target=target, limit=200)
    return any(r["filename"] == fn and r["checksum"] == cs for r in rows)
