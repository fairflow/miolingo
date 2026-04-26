"""Admin DB-health helpers: schema diff, row counts, per-user data audit.

Connects to BOTH local and remote regardless of which DB the app is
currently using — admin needs to see both sides. Local connection uses
``secrets['local_db']`` directly; remote connection uses an ephemeral
SSH tunnel via the existing pool helper.

Schema differences are filtered to suppress the noise that comes from
local being MySQL 8.0 (MacPorts) and remote being older (MariaDB / 5.7):

  * ``int`` ↔ ``int(11)``, ``bigint`` ↔ ``bigint(20)``  (display widths
    removed in MySQL 8.0)
  * ``CURRENT_TIMESTAMP`` ↔ ``current_timestamp()``  (function-call form
    on older versions)
  * ``DEFAULT_GENERATED`` extra ↔ empty string
  * Python ``None`` defaults ↔ string ``'NULL'`` defaults
  * Quoted enum/string defaults ``"'both'"`` ↔ unquoted ``'both'``

A "real" diff is anything left after that filter — missing columns,
missing indexes, type mismatches beyond version cosmetics.
"""
from __future__ import annotations

import re
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
import streamlit as st

import app_mysql


# ----------------------------------------------------------------------------
# Connections
# ----------------------------------------------------------------------------

def _local_connect():
    cfg = st.secrets["local_db"]
    socket_path = cfg.get("unix_socket", "")
    if socket_path:
        return mysql.connector.connect(
            unix_socket=socket_path,
            database=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            connect_timeout=10,
        )
    return mysql.connector.connect(
        host=cfg.get("host", "127.0.0.1"),
        port=int(cfg.get("port", 3306)),
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        connect_timeout=10,
    )


@contextmanager
def _remote_connect():
    """Ephemeral SSH-tunnelled connection to remote, regardless of mode."""
    pool = app_mysql.get_connection_pool_instance()
    with pool.get_bootstrap_connection() as conn:
        yield conn


def _local_db_name() -> str:
    return st.secrets["local_db"]["database"]


def _remote_db_name() -> str:
    return st.secrets["mysql"]["database"]


def local_enabled() -> bool:
    """True iff the app has ``local_db.enabled`` set, i.e. there *is* a
    local DB to compare against."""
    try:
        return bool(st.secrets.get("local_db", {}).get("enabled", False))
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Schema introspection
# ----------------------------------------------------------------------------

def _get_schema(conn, db_name: str) -> Dict[str, Dict[str, Any]]:
    c = conn.cursor(dictionary=True)
    c.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
        (db_name,),
    )
    table_names = [r["TABLE_NAME"] for r in c.fetchall()]

    schema: Dict[str, Dict[str, Any]] = {}
    for tbl in table_names:
        schema[tbl] = {"columns": {}, "indexes": {}}

        c.execute(
            "SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_DEFAULT, IS_NULLABLE, "
            "COLUMN_TYPE, EXTRA "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
            "ORDER BY ORDINAL_POSITION",
            (db_name, tbl),
        )
        for row in c.fetchall():
            schema[tbl]["columns"][row["COLUMN_NAME"]] = {
                "type":     row["COLUMN_TYPE"],
                "nullable": row["IS_NULLABLE"],
                "default":  row["COLUMN_DEFAULT"],
                "extra":    row["EXTRA"],
            }

        c.execute(
            "SELECT INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, NON_UNIQUE "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
            "ORDER BY INDEX_NAME, SEQ_IN_INDEX",
            (db_name, tbl),
        )
        idx: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in c.fetchall():
            idx[row["INDEX_NAME"]].append({
                "col": row["COLUMN_NAME"],
                "seq": row["SEQ_IN_INDEX"],
                "unique": row["NON_UNIQUE"] == 0,
            })
        schema[tbl]["indexes"] = dict(idx)
    c.close()
    return schema


# ----------------------------------------------------------------------------
# Cosmetic-difference filters
# ----------------------------------------------------------------------------

_INT_DISPLAY_WIDTH_RE = re.compile(r"^(tinyint|smallint|mediumint|int|bigint)\(\d+\)$")


def _normalise_type(t: Optional[str]) -> str:
    """Strip integer display widths so ``int`` and ``int(11)`` compare equal."""
    if t is None:
        return ""
    m = _INT_DISPLAY_WIDTH_RE.match(t.strip().lower())
    if m:
        return m.group(1)
    return t.strip().lower()


def _normalise_default(d: Any) -> str:
    """Make ``None`` / ``'NULL'`` / quoted enum literals all compare as the
    same value. Returns a canonical lowercase string."""
    if d is None:
        return ""
    s = str(d).strip()
    if s.upper() == "NULL":
        return ""
    # Strip surrounding single or double quotes (older MySQL quotes default
    # values for strings/enums).
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    if s.lower() in ("current_timestamp", "current_timestamp()"):
        return "current_timestamp"
    return s.lower()


def _normalise_extra(e: Optional[str]) -> str:
    """``DEFAULT_GENERATED`` is MySQL 8.0-specific noise — drop it."""
    if e is None:
        return ""
    parts = [p for p in re.split(r"\s+", e.strip()) if p and p.upper() != "DEFAULT_GENERATED"]
    # Lowercase ``current_timestamp()`` for the on-update clause.
    return " ".join(parts).lower().replace("current_timestamp()", "current_timestamp")


# ----------------------------------------------------------------------------
# Diff
# ----------------------------------------------------------------------------

def diff_schemas(
    local_schema: Dict[str, Dict[str, Any]],
    remote_schema: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return a list of structural differences. Each entry is a dict
    ``{table, kind, detail}`` where ``kind`` is one of:
      * ``table_missing_local`` / ``table_missing_remote``
      * ``column_missing_local`` / ``column_missing_remote``
      * ``column_type`` / ``column_nullable`` / ``column_default`` / ``column_extra``
      * ``index_missing_local`` / ``index_missing_remote`` / ``index_columns``

    Cosmetic differences (per ``_normalise_*``) are filtered out.
    """
    diffs: List[Dict[str, Any]] = []
    all_tables = sorted(set(local_schema) | set(remote_schema))

    for tbl in all_tables:
        L = local_schema.get(tbl)
        R = remote_schema.get(tbl)
        if L is None:
            diffs.append({"table": tbl, "kind": "table_missing_local", "detail": ""})
            continue
        if R is None:
            diffs.append({"table": tbl, "kind": "table_missing_remote", "detail": ""})
            continue

        # Columns
        all_cols = sorted(set(L["columns"]) | set(R["columns"]))
        for col in all_cols:
            if col not in L["columns"]:
                diffs.append({"table": tbl, "kind": "column_missing_local", "detail": col})
                continue
            if col not in R["columns"]:
                diffs.append({"table": tbl, "kind": "column_missing_remote", "detail": col})
                continue

            lc, rc = L["columns"][col], R["columns"][col]
            if _normalise_type(lc["type"]) != _normalise_type(rc["type"]):
                diffs.append({"table": tbl, "kind": "column_type",
                              "detail": f"{col}: LOCAL={lc['type']} REMOTE={rc['type']}"})
            if lc["nullable"] != rc["nullable"]:
                diffs.append({"table": tbl, "kind": "column_nullable",
                              "detail": f"{col}: LOCAL={lc['nullable']} REMOTE={rc['nullable']}"})
            if _normalise_default(lc["default"]) != _normalise_default(rc["default"]):
                diffs.append({"table": tbl, "kind": "column_default",
                              "detail": f"{col}: LOCAL={lc['default']!r} REMOTE={rc['default']!r}"})
            if _normalise_extra(lc["extra"]) != _normalise_extra(rc["extra"]):
                diffs.append({"table": tbl, "kind": "column_extra",
                              "detail": f"{col}: LOCAL={lc['extra']!r} REMOTE={rc['extra']!r}"})

        # Indexes
        all_idx = sorted(set(L["indexes"]) | set(R["indexes"]))
        for name in all_idx:
            if name not in L["indexes"]:
                cols = ", ".join(c["col"] for c in R["indexes"][name])
                diffs.append({"table": tbl, "kind": "index_missing_local",
                              "detail": f"{name} ({cols})"})
                continue
            if name not in R["indexes"]:
                cols = ", ".join(c["col"] for c in L["indexes"][name])
                diffs.append({"table": tbl, "kind": "index_missing_remote",
                              "detail": f"{name} ({cols})"})
                continue
            l_cols = [c["col"] for c in L["indexes"][name]]
            r_cols = [c["col"] for c in R["indexes"][name]]
            if l_cols != r_cols:
                diffs.append({"table": tbl, "kind": "index_columns",
                              "detail": f"{name}: LOCAL=({', '.join(l_cols)}) REMOTE=({', '.join(r_cols)})"})

    return diffs


# ----------------------------------------------------------------------------
# Row counts
# ----------------------------------------------------------------------------

def _table_count(conn, table: str) -> int:
    c = conn.cursor()
    try:
        c.execute(f"SELECT COUNT(*) FROM `{table}`")
        n = c.fetchone()[0]
    finally:
        c.close()
    return int(n)


def row_counts() -> List[Dict[str, Any]]:
    """Return a list of ``{table, local, remote}`` for every table present
    in either DB. Tables missing from one side show ``-`` there."""
    rows: List[Dict[str, Any]] = []
    local_tables: List[str] = []
    remote_tables: List[str] = []

    if local_enabled():
        with _local_connect() as lc:
            ls = _get_schema(lc, _local_db_name())
            local_tables = list(ls.keys())
            local_counts = {t: _table_count(lc, t) for t in local_tables}
    else:
        local_counts = {}

    with _remote_connect() as rc:
        rs = _get_schema(rc, _remote_db_name())
        remote_tables = list(rs.keys())
        remote_counts = {t: _table_count(rc, t) for t in remote_tables}

    all_tables = sorted(set(local_tables) | set(remote_tables))
    for t in all_tables:
        rows.append({
            "table": t,
            "local":  local_counts.get(t, "-"),
            "remote": remote_counts.get(t, "-"),
            "diff":   (
                (local_counts.get(t, 0) - remote_counts.get(t, 0))
                if t in local_counts and t in remote_counts else "-"
            ),
        })
    return rows


# ----------------------------------------------------------------------------
# Per-user audit
# ----------------------------------------------------------------------------

_PER_USER_TABLES = (
    "vocab_entries",
    "user_progress",
    "user_settings",
    "sessions",
    "activity_log",
)


def per_user_audit(user_id: int) -> List[Dict[str, Any]]:
    """For each per-user table, return ``{table, local, remote}`` row counts
    filtered by ``user_id``."""
    out: List[Dict[str, Any]] = []
    for t in _PER_USER_TABLES:
        local_n: Any = "-"
        remote_n: Any = "-"
        if local_enabled():
            try:
                with _local_connect() as lc:
                    c = lc.cursor()
                    c.execute(f"SELECT COUNT(*) FROM `{t}` WHERE user_id = %s", (user_id,))
                    local_n = int(c.fetchone()[0])
                    c.close()
            except Exception:
                local_n = "err"
        try:
            with _remote_connect() as rc:
                c = rc.cursor()
                c.execute(f"SELECT COUNT(*) FROM `{t}` WHERE user_id = %s", (user_id,))
                remote_n = int(c.fetchone()[0])
                c.close()
        except Exception:
            remote_n = "err"
        out.append({"table": t, "local": local_n, "remote": remote_n})
    return out


# ----------------------------------------------------------------------------
# High-level entry: full schema comparison
# ----------------------------------------------------------------------------

def full_diff() -> Tuple[List[Dict[str, Any]], int, int]:
    """Returns ``(diffs, local_table_count, remote_table_count)``.

    ``diffs`` is empty (or short) when the schemas are functionally
    identical — version cosmetics are filtered.
    """
    if not local_enabled():
        with _remote_connect() as rc:
            rs = _get_schema(rc, _remote_db_name())
        return [], 0, len(rs)

    with _local_connect() as lc:
        ls = _get_schema(lc, _local_db_name())
    with _remote_connect() as rc:
        rs = _get_schema(rc, _remote_db_name())
    return diff_schemas(ls, rs), len(ls), len(rs)
