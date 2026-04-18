"""
Integration-test fixtures. Target: a local MySQL instance via Unix socket
(the `local_db` block in `.streamlit/secrets.toml`).

Session-scoped: create throwaway DB `miolingo_test`, apply schema.sql, drop on
teardown.

Function-scoped: open a fresh connection, truncate all tables after each test.
app_mysql.get_connection() is monkeypatched per-test so product code is routed
at the same DB.

Requires `local_db.enabled = true` in secrets.toml. If absent, tests are
skipped rather than failed — this keeps `pytest` green for users without a
local MySQL setup (e.g. CI before we wire a MySQL service).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

import pytest

try:
    import mysql.connector
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    mysql = None  # type: ignore

TEST_DB_NAME = os.environ.get("MIOLINGO_TEST_DB_NAME", "miolingo_test")

_SECRETS_CANDIDATES = [
    # Worktree-local (if the user symlinked it in — see project_worktree_secrets memory)
    Path(__file__).resolve().parent.parent.parent / ".streamlit" / "secrets.toml",
    # Main repo checkout, one level up from any worktree
    Path("/Users/matthew/Software/working/miolingo/.streamlit/secrets.toml"),
    # Streamlit global location
    Path.home() / ".streamlit" / "secrets.toml",
]


def _load_local_db_creds() -> Optional[dict]:
    """Return the [local_db] block from secrets.toml, or None if unavailable."""
    for path in _SECRETS_CANDIDATES:
        if not path.exists():
            continue
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            continue
        block = data.get("local_db")
        if block and block.get("enabled"):
            return block
    return None


def _connect_kwargs(creds: dict, database: Optional[str] = None) -> dict:
    kwargs = {
        "user": creds["user"],
        "password": creds["password"],
    }
    if creds.get("unix_socket"):
        kwargs["unix_socket"] = creds["unix_socket"]
    else:
        kwargs["host"] = creds.get("host", "127.0.0.1")
        kwargs["port"] = creds.get("port", 3306)
    if database:
        kwargs["database"] = database
    return kwargs


@pytest.fixture(scope="session")
def db_creds() -> dict:
    if mysql is None:
        pytest.skip("mysql-connector-python not installed")
    creds = _load_local_db_creds()
    if not creds:
        pytest.skip(
            "No local_db block in secrets.toml — see tests/integration/README.md "
            "to enable."
        )
    return creds


@pytest.fixture(scope="session")
def test_db(db_creds: dict) -> str:
    """Apply schema.sql to the pre-existing `miolingo_test` database.

    The database itself must be created once, out of band, by a MySQL admin —
    the `local_db.user` is not granted CREATE/DROP DATABASE. See
    tests/integration/README.md for the one-time setup.

    The fixture drops all existing tables in `miolingo_test` and reapplies the
    dumped schema, so each test run starts clean.
    """
    try:
        admin = mysql.connector.connect(
            **_connect_kwargs(db_creds, database=TEST_DB_NAME)
        )
    except mysql.connector.errors.ProgrammingError as e:
        pytest.skip(
            f"Cannot connect to test DB '{TEST_DB_NAME}': {e}. "
            "See tests/integration/README.md for one-time setup."
        )
    cur = admin.cursor()

    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = %s",
        (TEST_DB_NAME,),
    )
    for (tbl,) in cur.fetchall():
        cur.execute(f"DROP TABLE IF EXISTS `{tbl}`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")

    schema_sql = (Path(__file__).parent / "schema.sql").read_text()
    # Match the production sql_mode that generated the dump — the live
    # schema has `timestamp NOT NULL DEFAULT '0000-00-00 00:00:00'` which
    # MySQL 8 strict mode rejects. NO_ZERO_DATE/NO_ZERO_IN_DATE off for the
    # session so DDL applies; tests don't depend on strict-mode behaviour.
    cur.execute(
        "SET SESSION sql_mode = 'NO_ENGINE_SUBSTITUTION'"
    )
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for stmt in _split_sql_statements(schema_sql):
        cur.execute(stmt)
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    admin.commit()
    cur.close()
    admin.close()

    yield TEST_DB_NAME


def _split_sql_statements(sql: str) -> list[str]:
    """Naive statement splitter — fine for pure DDL without stored procedures."""
    statements = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).rstrip(";").strip())
            buf = []
    return [s for s in statements if s]


class _FakePool:
    """Minimal pool stand-in: routes all connection paths to the test conn.

    Product code calls either `app_mysql.get_connection()` (monkeypatched
    separately) or `pool.get_bootstrap_connection()` (context manager). We
    alias both to the same test connection so every query lands in
    `miolingo_test`, not the remote production DB.
    """

    def __init__(self, conn):
        self._conn = conn

    def get_bootstrap_connection(self):
        return _CtxConn(self._conn)

    # Some call sites also do `with pool.get_connection() as c:` — same deal.
    def get_connection(self):
        return _CtxConn(self._conn)


class _CtxConn:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc):
        # Don't close — the test fixture owns the connection lifetime.
        return False


@pytest.fixture
def db_conn(test_db: str, db_creds: dict, monkeypatch):
    """Per-test connection on the test DB. Truncates every table after the test.

    Monkeypatches `app_mysql.get_connection()` AND the connection pool's
    bootstrap path so every product-code connection hits the test DB.
    """
    conn = mysql.connector.connect(**_connect_kwargs(db_creds, database=test_db))
    conn.autocommit = True

    import app_mysql

    fake_pool = _FakePool(conn)
    monkeypatch.setattr(app_mysql, "get_connection", lambda: conn)
    monkeypatch.setattr(app_mysql, "get_connection_pool_instance", lambda: fake_pool)

    # delete_session() reads `st.session_state['db_connection']` — populate it
    # so logout paths operate on the test DB.
    import streamlit as st
    st.session_state["db_connection"] = conn

    yield conn

    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = %s",
        (test_db,),
    )
    tables = [row[0] for row in cur.fetchall()]
    for t in tables:
        cur.execute(f"TRUNCATE TABLE `{t}`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    cur.close()
    conn.close()


@pytest.fixture
def make_user(db_conn):
    """Factory: create a real user via app_mysql.create_user and return a dict
    with user_id, username, email, password (plaintext for login tests).
    """
    import app_mysql

    counter = {"n": 0}

    def _make(username: Optional[str] = None, password: str = "TestPass123!") -> dict:
        counter["n"] += 1
        uname = username or f"testuser{counter['n']}"
        email = f"{uname}@example.com"
        user_id = app_mysql.create_user(uname, email, password)
        assert user_id, "create_user returned None — check schema / unique constraints"
        return {
            "user_id": user_id,
            "username": uname,
            "email": email,
            "password": password,
        }

    return _make
