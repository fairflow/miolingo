#!/usr/bin/env python3
"""
sync_db.py — Bidirectional sync between local and remote Miolingo MySQL databases.

Usage:
    python scripts/sync_db.py                 # normal sync (since last run)
    python scripts/sync_db.py --full          # full re-sync from epoch
    python scripts/sync_db.py --dry-run       # show what would sync, don't write

Requires:
    - Local MySQL with fairtlou_miolingo database (see export_schema.sh)
    - SSH access to miolingo.io:722
    - Python packages: mysql-connector-python, sshtunnel, paramiko

Run from the project root so it can find .streamlit/secrets.toml for credentials.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import mysql.connector
from sshtunnel import SSHTunnelForwarder

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SYNC_STATE_FILE = Path.home() / ".miolingo" / "last_sync.json"

# Tables and their sync strategies
SYNC_TABLES = {
    "users":             {"direction": "remote_to_local", "strategy": "overwrite"},
    "user_progress":     {"direction": "bidirectional",   "strategy": "append_by_date"},
    "user_settings":     {"direction": "bidirectional",   "strategy": "last_write_wins"},
    "translation_cache": {"direction": "bidirectional",   "strategy": "insert_ignore"},
    "announcements":     {"direction": "remote_to_local", "strategy": "overwrite"},
    "activity_log":      {"direction": "remote_to_local", "strategy": "append_by_date"},
}

# Tables skipped (infrastructure-local)
SKIP_TABLES = ["sessions", "tunnel_monitor", "connection_monitor", "debug_logs", "rate_limits"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sync_db")


# ---------------------------------------------------------------------------
# Credentials (read from .streamlit/secrets.toml via tomllib or toml)
# ---------------------------------------------------------------------------

def _load_secrets() -> dict:
    """Parse .streamlit/secrets.toml and return as nested dict."""
    secrets_path = Path(".streamlit/secrets.toml")
    if not secrets_path.exists():
        secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        sys.exit(f"Cannot find secrets.toml (tried CWD and script parent)")

    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # pip install tomli for <3.11
        except ImportError:
            sys.exit("Need Python 3.11+ (tomllib) or 'pip install tomli' to parse secrets.toml")

    with open(secrets_path, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def open_remote_connection(secrets: dict) -> tuple[SSHTunnelForwarder, mysql.connector.MySQLConnection]:
    """Open SSH tunnel + MySQL connection to remote."""
    ssh = secrets["ssh"]
    db = secrets["mysql"]

    import paramiko
    from io import StringIO

    # Parse SSH key
    ssh_key = None
    if "key_content" in ssh:
        key_file = StringIO(ssh["key_content"])
        for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                key_file.seek(0)
                ssh_key = key_class.from_private_key(key_file)
                break
            except Exception:
                continue
        if ssh_key is None:
            sys.exit("Could not parse SSH key from secrets")
    else:
        ssh_key = str(Path(ssh["key_path"]).expanduser())

    tunnel = SSHTunnelForwarder(
        (ssh["host"], int(ssh["port"])),
        ssh_username=ssh["username"],
        ssh_pkey=ssh_key,
        remote_bind_address=("127.0.0.1", 3306),
        set_keepalive=30.0,
    )
    tunnel.start()

    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=tunnel.local_bind_port,
        database=db["database"],
        user=db["user"],
        password=db["password"],
        autocommit=False,
    )
    log.info(f"Remote: connected via tunnel (local port {tunnel.local_bind_port})")
    return tunnel, conn


def open_local_connection(secrets: dict) -> mysql.connector.MySQLConnection:
    """Open direct connection to local MySQL."""
    cfg = secrets["local_db"]
    conn = mysql.connector.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        autocommit=False,
    )
    log.info("Local: connected")
    return conn


# ---------------------------------------------------------------------------
# Sync state persistence
# ---------------------------------------------------------------------------

def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text())
    return {}


def save_sync_state(state: dict):
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ---------------------------------------------------------------------------
# Table existence check
# ---------------------------------------------------------------------------

def _table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SHOW TABLES LIKE %s", (table_name,))
    result = cur.fetchone()
    cur.close()
    return result is not None


# ---------------------------------------------------------------------------
# Sync strategies
# ---------------------------------------------------------------------------

def _get_columns(conn, table: str) -> list[str]:
    """Get column names for a table, excluding auto-increment PKs."""
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = cur.fetchall()
    cur.close()
    # Exclude auto-increment columns (they're local PKs)
    return [c["Field"] for c in cols if "auto_increment" not in c.get("Extra", "")]


def _get_all_columns(conn, table: str) -> list[str]:
    """Get ALL column names including auto-increment PKs."""
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = cur.fetchall()
    cur.close()
    return [c["Field"] for c in cols]


def sync_overwrite(
    source_conn, dest_conn, table: str, dry_run: bool = False
) -> dict:
    """Remote → Local overwrite: truncate dest, copy all from source."""
    stats = {"table": table, "strategy": "overwrite", "rows_copied": 0}

    all_cols = _get_all_columns(source_conn, table)
    col_list = ", ".join(f"`{c}`" for c in all_cols)

    src_cur = source_conn.cursor(dictionary=True)
    src_cur.execute(f"SELECT {col_list} FROM `{table}`")
    rows = src_cur.fetchall()
    src_cur.close()
    stats["rows_copied"] = len(rows)

    if dry_run:
        log.info(f"  [DRY RUN] {table}: would overwrite {len(rows)} rows")
        return stats

    dest_cur = dest_conn.cursor()
    dest_cur.execute(f"DELETE FROM `{table}`")
    if rows:
        placeholders = ", ".join(["%s"] * len(all_cols))
        insert_sql = f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})"
        for row in rows:
            dest_cur.execute(insert_sql, tuple(row[c] for c in all_cols))
    dest_conn.commit()
    dest_cur.close()

    log.info(f"  {table}: overwrote with {len(rows)} rows from remote")
    return stats


def sync_append_by_date(
    local_conn, remote_conn, table: str, last_sync_ts: str,
    date_col: str = "practice_date", dry_run: bool = False
) -> dict:
    """Bidirectional append using a date column as the watermark."""
    stats = {"table": table, "strategy": "append_by_date",
             "local_to_remote": 0, "remote_to_local": 0, "skipped_dupes": 0}

    # Use non-PK columns for insert (let each side auto-assign its own PK)
    cols = _get_columns(local_conn, table)
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})"

    # --- Local → Remote ---
    lcur = local_conn.cursor(dictionary=True)
    lcur.execute(
        f"SELECT {col_list} FROM `{table}` WHERE `{date_col}` > %s",
        (last_sync_ts,),
    )
    new_local = lcur.fetchall()
    lcur.close()

    if new_local:
        if dry_run:
            log.info(f"  [DRY RUN] {table}: would push {len(new_local)} rows → remote")
        else:
            rcur = remote_conn.cursor()
            for row in new_local:
                try:
                    rcur.execute(insert_sql, tuple(row[c] for c in cols))
                    stats["local_to_remote"] += 1
                except mysql.connector.IntegrityError:
                    stats["skipped_dupes"] += 1
            remote_conn.commit()
            rcur.close()
            log.info(f"  {table}: pushed {stats['local_to_remote']} rows → remote")

    # --- Remote → Local ---
    rcur = remote_conn.cursor(dictionary=True)
    rcur.execute(
        f"SELECT {col_list} FROM `{table}` WHERE `{date_col}` > %s",
        (last_sync_ts,),
    )
    new_remote = rcur.fetchall()
    rcur.close()

    if new_remote:
        if dry_run:
            log.info(f"  [DRY RUN] {table}: would pull {len(new_remote)} rows ← remote")
        else:
            lcur = local_conn.cursor()
            for row in new_remote:
                try:
                    lcur.execute(insert_sql, tuple(row[c] for c in cols))
                    stats["remote_to_local"] += 1
                except mysql.connector.IntegrityError:
                    stats["skipped_dupes"] += 1
            local_conn.commit()
            lcur.close()
            log.info(f"  {table}: pulled {stats['remote_to_local']} rows ← remote")

    return stats


def sync_last_write_wins(
    local_conn, remote_conn, table: str, dry_run: bool = False
) -> dict:
    """Bidirectional merge on (user_id, setting_key) using updated_at."""
    stats = {"table": table, "strategy": "last_write_wins",
             "local_to_remote": 0, "remote_to_local": 0}

    all_cols = _get_all_columns(local_conn, table)
    col_list = ", ".join(f"`{c}`" for c in all_cols)

    # Fetch everything from both sides
    lcur = local_conn.cursor(dictionary=True)
    lcur.execute(f"SELECT {col_list} FROM `{table}`")
    local_rows = {(r["user_id"], r.get("setting_key", "")): r for r in lcur.fetchall()}
    lcur.close()

    rcur = remote_conn.cursor(dictionary=True)
    rcur.execute(f"SELECT {col_list} FROM `{table}`")
    remote_rows = {(r["user_id"], r.get("setting_key", "")): r for r in rcur.fetchall()}
    rcur.close()

    all_keys = set(local_rows.keys()) | set(remote_rows.keys())
    non_pk_cols = _get_columns(local_conn, table)
    non_pk_col_list = ", ".join(f"`{c}`" for c in non_pk_cols)
    placeholders = ", ".join(["%s"] * len(non_pk_cols))

    for key in all_keys:
        l_row = local_rows.get(key)
        r_row = remote_rows.get(key)

        if l_row and not r_row:
            # Only on local → push to remote
            if not dry_run:
                rcur = remote_conn.cursor()
                rcur.execute(
                    f"INSERT INTO `{table}` ({non_pk_col_list}) VALUES ({placeholders})",
                    tuple(l_row[c] for c in non_pk_cols),
                )
                rcur.close()
            stats["local_to_remote"] += 1
        elif r_row and not l_row:
            # Only on remote → pull to local
            if not dry_run:
                lcur = local_conn.cursor()
                lcur.execute(
                    f"INSERT INTO `{table}` ({non_pk_col_list}) VALUES ({placeholders})",
                    tuple(r_row[c] for c in non_pk_cols),
                )
                lcur.close()
            stats["remote_to_local"] += 1
        else:
            # Both exist — compare updated_at
            l_ts = l_row.get("updated_at", datetime.min)
            r_ts = r_row.get("updated_at", datetime.min)

            if l_ts > r_ts:
                # Local wins → update remote
                if not dry_run:
                    set_clause = ", ".join(f"`{c}` = %s" for c in non_pk_cols)
                    rcur = remote_conn.cursor()
                    rcur.execute(
                        f"UPDATE `{table}` SET {set_clause} WHERE user_id = %s",
                        tuple(l_row[c] for c in non_pk_cols) + (key[0],),
                    )
                    rcur.close()
                stats["local_to_remote"] += 1
            elif r_ts > l_ts:
                # Remote wins → update local
                if not dry_run:
                    set_clause = ", ".join(f"`{c}` = %s" for c in non_pk_cols)
                    lcur = local_conn.cursor()
                    lcur.execute(
                        f"UPDATE `{table}` SET {set_clause} WHERE user_id = %s",
                        tuple(r_row[c] for c in non_pk_cols) + (key[0],),
                    )
                    lcur.close()
                stats["remote_to_local"] += 1

    if not dry_run:
        local_conn.commit()
        remote_conn.commit()

    log.info(f"  {table}: L→R {stats['local_to_remote']}, R→L {stats['remote_to_local']}")
    return stats


def sync_insert_ignore(
    local_conn, remote_conn, table: str, dry_run: bool = False
) -> dict:
    """Bidirectional insert-ignore: copy rows that don't exist on the other side."""
    stats = {"table": table, "strategy": "insert_ignore",
             "local_to_remote": 0, "remote_to_local": 0}

    cols = _get_columns(local_conn, table)
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))

    # Local → Remote
    lcur = local_conn.cursor(dictionary=True)
    lcur.execute(f"SELECT {col_list} FROM `{table}`")
    local_rows = lcur.fetchall()
    lcur.close()

    if local_rows and not dry_run:
        rcur = remote_conn.cursor()
        for row in local_rows:
            try:
                rcur.execute(
                    f"INSERT IGNORE INTO `{table}` ({col_list}) VALUES ({placeholders})",
                    tuple(row[c] for c in cols),
                )
                if rcur.rowcount > 0:
                    stats["local_to_remote"] += 1
            except mysql.connector.IntegrityError:
                pass
        remote_conn.commit()
        rcur.close()

    # Remote → Local
    rcur = remote_conn.cursor(dictionary=True)
    rcur.execute(f"SELECT {col_list} FROM `{table}`")
    remote_rows = rcur.fetchall()
    rcur.close()

    if remote_rows and not dry_run:
        lcur = local_conn.cursor()
        for row in remote_rows:
            try:
                lcur.execute(
                    f"INSERT IGNORE INTO `{table}` ({col_list}) VALUES ({placeholders})",
                    tuple(row[c] for c in cols),
                )
                if lcur.rowcount > 0:
                    stats["remote_to_local"] += 1
            except mysql.connector.IntegrityError:
                pass
        local_conn.commit()
        lcur.close()

    if dry_run:
        log.info(f"  [DRY RUN] {table}: {len(local_rows)} local, {len(remote_rows)} remote")
    else:
        log.info(f"  {table}: L→R {stats['local_to_remote']}, R→L {stats['remote_to_local']}")
    return stats


# ---------------------------------------------------------------------------
# Main sync orchestrator
# ---------------------------------------------------------------------------

def run_sync(full: bool = False, dry_run: bool = False):
    secrets = _load_secrets()

    if not secrets.get("local_db", {}).get("enabled", False):
        # Even if local_db isn't enabled in the app, the sync script still
        # needs local credentials.  Allow running if the section exists.
        if "local_db" not in secrets:
            sys.exit("[local_db] section missing from .streamlit/secrets.toml")

    state = load_sync_state()
    last_sync_ts = "1970-01-01 00:00:00" if full else state.get(
        "last_sync_ts", "1970-01-01 00:00:00"
    )
    log.info(f"Sync since: {last_sync_ts}  {'(FULL)' if full else ''}")
    sync_start = datetime.now()

    # Open connections
    tunnel, remote_conn = open_remote_connection(secrets)
    local_conn = open_local_connection(secrets)

    all_stats = []
    try:
        for table, cfg in SYNC_TABLES.items():
            # Check table exists on both sides
            if not _table_exists(local_conn, table):
                log.warning(f"  {table}: not found locally — skipping")
                continue
            if not _table_exists(remote_conn, table):
                log.warning(f"  {table}: not found on remote — skipping")
                continue

            direction = cfg["direction"]
            strategy = cfg["strategy"]

            log.info(f"Syncing {table} ({direction} / {strategy})...")

            if strategy == "overwrite":
                stats = sync_overwrite(remote_conn, local_conn, table, dry_run)
            elif strategy == "append_by_date":
                date_col = "practice_date" if table == "user_progress" else "created_at"
                stats = sync_append_by_date(
                    local_conn, remote_conn, table, last_sync_ts,
                    date_col=date_col, dry_run=dry_run,
                )
            elif strategy == "last_write_wins":
                stats = sync_last_write_wins(local_conn, remote_conn, table, dry_run)
            elif strategy == "insert_ignore":
                stats = sync_insert_ignore(local_conn, remote_conn, table, dry_run)
            else:
                log.warning(f"  Unknown strategy {strategy} for {table}")
                continue

            all_stats.append(stats)

    finally:
        local_conn.close()
        remote_conn.close()
        tunnel.stop()

    # Persist sync timestamp
    if not dry_run:
        state["last_sync_ts"] = sync_start.isoformat()
        state["last_sync_tables"] = [s["table"] for s in all_stats]
        save_sync_state(state)
        log.info(f"Sync complete — state saved to {SYNC_STATE_FILE}")
    else:
        log.info("Dry run complete — no changes written.")

    return all_stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Miolingo DB sync (local ↔ remote)")
    parser.add_argument("--full", action="store_true", help="Full re-sync from epoch")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't write")
    args = parser.parse_args()

    run_sync(full=args.full, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
