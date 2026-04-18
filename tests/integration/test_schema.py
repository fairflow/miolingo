"""
Integration tests: schema sanity — ensure the dumped schema applied cleanly
and exposes the tables and key columns product code relies on.

If these fail after a schema.sql refresh, the dump is likely stale or the
production schema drifted from what the app expects.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

REQUIRED_TABLES = {
    "users",
    "sessions",
    "user_progress",
    "user_settings",
    "activity_log",
    "announcements",
    "rate_limits",
    "debug_logs",
}


def _table_names(conn, schema: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
        (schema,),
    )
    return {row[0] for row in cur.fetchall()}


def _columns(conn, schema: str, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (schema, table),
    )
    return {row[0] for row in cur.fetchall()}


def test_required_tables_exist(db_conn):
    tables = _table_names(db_conn, "miolingo_test")
    missing = REQUIRED_TABLES - tables
    assert not missing, f"Missing tables in test schema: {missing}"


def test_users_table_has_auth_columns(db_conn):
    cols = _columns(db_conn, "miolingo_test", "users")
    for expected in ("user_id", "username", "email", "password_hash"):
        assert expected in cols, f"users.{expected} missing"


def test_sessions_table_has_lifecycle_columns(db_conn):
    cols = _columns(db_conn, "miolingo_test", "sessions")
    for expected in ("session_id", "user_id", "status", "expires_at", "last_activity"):
        assert expected in cols, f"sessions.{expected} missing"


def test_user_progress_has_scoring_columns(db_conn):
    cols = _columns(db_conn, "miolingo_test", "user_progress")
    for expected in (
        "user_id",
        "language_code",
        "target_phrase",
        "recognized_phrase",
        "similarity_score",
        "perfect_match",
    ):
        assert expected in cols, f"user_progress.{expected} missing"
