"""Selective table sync between LOCAL and REMOTE DBs.

Used by the admin Sync tab to copy rows from one DB to the other under
one of three conflict policies:

* ``skip`` — only insert rows whose unique key is missing on the target;
  existing rows are left alone.
* ``overwrite`` — upsert every source row; existing rows are replaced.
* ``merge-by-timestamp`` — for each row, compare the source row's
  freshness column against the target's; only apply rows where source
  is newer (or target row is missing). Per-table freshness column is
  declared in ``SYNCABLE_TABLES``.

Only tables explicitly registered in ``SYNCABLE_TABLES`` are syncable —
admin can't choose arbitrary tables. Each entry declares the unique
columns (used to detect overlap) and an optional freshness column
(required for merge-by-timestamp).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import admin_db_health


# ----------------------------------------------------------------------------
# Whitelist
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class SyncSpec:
    table:             str
    unique_columns:    Tuple[str, ...]
    freshness_column:  Optional[str]   # ``None`` => merge-by-timestamp not supported
    description:       str


SYNCABLE_TABLES: Dict[str, SyncSpec] = {
    "translation_cache": SyncSpec(
        table="translation_cache",
        unique_columns=("provider", "source_lang", "target_lang", "source_text_hash"),
        freshness_column="updated_at",
        description="Cached translations. Cheap to merge — pure read cache.",
    ),
    "vocab_entries": SyncSpec(
        table="vocab_entries",
        unique_columns=("user_id", "language_code", "source_language_code", "word"),
        freshness_column="last_seen_at",
        description="Per-user vocab. Merge-by-timestamp picks the most "
                    "recently practised row's translation/IPA/counters.",
    ),
    "user_settings": SyncSpec(
        table="user_settings",
        unique_columns=("user_id", "setting_key"),
        freshness_column="updated_at",
        description="Per-user settings. Already dual-written by the app; "
                    "this is a recovery tool for drift.",
    ),
}

VALID_POLICIES = ("skip", "overwrite", "merge-by-timestamp")


# ----------------------------------------------------------------------------
# Connection helpers — reuse what admin_db_health already exposes
# ----------------------------------------------------------------------------

def _open(target: str):
    """Return an already-opened connection. Caller is responsible for
    closing remote connections via the context manager pattern; for
    consistency this returns a *closeable* object that callers must close.
    """
    if target == "local":
        if not admin_db_health.local_enabled():
            raise RuntimeError("Local DB is disabled in secrets.toml.")
        return admin_db_health._local_connect()
    if target == "remote":
        # Open a fresh tunnel + conn; the caller must close it.
        # admin_db_health._remote_connect is a contextmanager that owns
        # the tunnel — for the manual close pattern we open via the pool
        # directly so we can hold the connection across multiple statements.
        import app_mysql
        pool = app_mysql.get_connection_pool_instance()
        # The pool's bootstrap is REMOTE-ONLY (post PR-1 docstring). Use
        # the pool's create_ssh_tunnel + manual connect so we can keep the
        # tunnel + conn alive for the duration of the sync.
        tunnel = pool.create_ssh_tunnel()
        import mysql.connector
        conn = mysql.connector.connect(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            database=pool.secrets["mysql"]["database"],
            user=pool.secrets["mysql"]["user"],
            password=pool.secrets["mysql"]["password"],
            connect_timeout=10,
        )
        # Stash the tunnel on the connection so close() also stops it.
        conn._sync_tunnel = tunnel  # type: ignore[attr-defined]
        return conn
    raise ValueError(f"Unknown target {target!r}")


def _close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass
    tunnel = getattr(conn, "_sync_tunnel", None)
    if tunnel is not None:
        try:
            tunnel.stop()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Preview — count source / target / overlap before syncing
# ----------------------------------------------------------------------------

def preview(table: str, source: str, target: str) -> Dict[str, Any]:
    """Return ``{source_count, target_count, overlap, source_only,
    target_only}`` so admin can see what's about to happen."""
    if table not in SYNCABLE_TABLES:
        raise ValueError(f"Table {table!r} is not in the sync whitelist.")
    if source == target:
        raise ValueError("Source and target must differ.")

    spec = SYNCABLE_TABLES[table]
    src = _open(source)
    tgt = _open(target)
    try:
        sc = src.cursor()
        tc = tgt.cursor()
        sc.execute(f"SELECT COUNT(*) FROM `{table}`")
        source_count = int(sc.fetchone()[0])
        tc.execute(f"SELECT COUNT(*) FROM `{table}`")
        target_count = int(tc.fetchone()[0])

        # Build the unique-key tuples on each side.
        cols_csv = ", ".join(f"`{c}`" for c in spec.unique_columns)
        sc.execute(f"SELECT {cols_csv} FROM `{table}`")
        src_keys = {tuple(r) for r in sc.fetchall()}
        tc.execute(f"SELECT {cols_csv} FROM `{table}`")
        tgt_keys = {tuple(r) for r in tc.fetchall()}

        overlap = src_keys & tgt_keys
        source_only = src_keys - tgt_keys
        target_only = tgt_keys - src_keys

        sc.close()
        tc.close()
    finally:
        _close(src)
        _close(tgt)

    return {
        "source_count": source_count,
        "target_count": target_count,
        "overlap":      len(overlap),
        "source_only":  len(source_only),
        "target_only":  len(target_only),
    }


# ----------------------------------------------------------------------------
# Sync
# ----------------------------------------------------------------------------

def _column_names(conn, table: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM `{table}` LIMIT 0")
    cols = [d[0] for d in cur.description]
    cur.close()
    return cols


def _fetch_all(conn, table: str, columns: List[str]) -> List[Dict[str, Any]]:
    cols_csv = ", ".join(f"`{c}`" for c in columns)
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SELECT {cols_csv} FROM `{table}`")
    rows = cur.fetchall()
    cur.close()
    return rows


def _index_by_key(rows: List[Dict[str, Any]], spec: SyncSpec) -> Dict[Tuple, Dict[str, Any]]:
    return {tuple(r[c] for c in spec.unique_columns): r for r in rows}


def _executemany_upsert(
    conn,
    table: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    chunk_size: int = 500,
) -> None:
    """``INSERT ... ON DUPLICATE KEY UPDATE col=VALUES(col)`` for every
    column. Caller has already filtered ``rows`` to exactly those it
    wants to apply, so a blanket "overwrite all non-key columns" is
    correct here regardless of the original policy."""
    if not rows:
        return
    cols_csv = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    update_csv = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in columns)
    sql = (
        f"INSERT INTO `{table}` ({cols_csv}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {update_csv}"
    )
    cur = conn.cursor()
    try:
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            params = [tuple(r[c] for c in columns) for r in chunk]
            cur.executemany(sql, params)
        conn.commit()
    finally:
        cur.close()


def sync_table(
    table: str,
    *,
    source: str,
    target: str,
    policy: str,
) -> Dict[str, Any]:
    """Apply rows from ``source`` to ``target`` under ``policy``.

    Returns ``{table, source, target, policy, selected, applied, skipped}``.
    ``selected`` is rows fetched from source; ``applied`` is rows actually
    sent to target after policy filtering; ``skipped = selected - applied``.
    """
    if table not in SYNCABLE_TABLES:
        raise ValueError(f"Table {table!r} is not in the sync whitelist.")
    if policy not in VALID_POLICIES:
        raise ValueError(f"policy must be one of {VALID_POLICIES}, got {policy!r}")
    if source == target:
        raise ValueError("Source and target must differ.")
    spec = SYNCABLE_TABLES[table]
    if policy == "merge-by-timestamp" and spec.freshness_column is None:
        raise ValueError(
            f"Table {table!r} has no freshness column; merge-by-timestamp "
            "is not supported for it."
        )

    src = _open(source)
    tgt = _open(target)
    try:
        # Same column set on both sides so the upsert SQL matches.
        src_cols = _column_names(src, table)
        tgt_cols = _column_names(tgt, table)
        # Use the intersection so we don't break on schema drift.
        common_cols = [c for c in src_cols if c in tgt_cols]
        if any(c not in common_cols for c in spec.unique_columns):
            raise RuntimeError(
                f"Schema drift: unique columns {spec.unique_columns} not all "
                "present on both sides. Run a schema diff first."
            )

        src_rows = _fetch_all(src, table, common_cols)

        if policy == "overwrite":
            to_apply = src_rows
        else:
            tgt_rows = _fetch_all(tgt, table, common_cols)
            tgt_index = _index_by_key(tgt_rows, spec)
            to_apply = []
            for r in src_rows:
                key = tuple(r[c] for c in spec.unique_columns)
                existing = tgt_index.get(key)
                if existing is None:
                    to_apply.append(r)
                elif policy == "merge-by-timestamp":
                    fc = spec.freshness_column
                    if fc and r[fc] is not None and (
                        existing[fc] is None or r[fc] > existing[fc]
                    ):
                        to_apply.append(r)
                # ``skip``: existing row → drop

        _executemany_upsert(tgt, table, common_cols, to_apply)

    finally:
        _close(src)
        _close(tgt)

    return {
        "table":    table,
        "source":   source,
        "target":   target,
        "policy":   policy,
        "selected": len(src_rows),
        "applied":  len(to_apply),
        "skipped":  len(src_rows) - len(to_apply),
    }
