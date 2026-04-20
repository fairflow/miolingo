#!/usr/bin/env python3
"""
check_vocab_sync.py — Read-only diagnostic for vocab_entries sync state.

Connects to both local and remote MySQL and reports:
  - Row counts per user/language on each side
  - Words present locally but not remotely (and vice versa)
  - Whether vocab_entries is registered in sync_db.py's SYNC_TABLES
  - Last sync timestamp

Usage:
    source venv/bin/activate
    python scripts/check_vocab_sync.py            # full diff
    python scripts/check_vocab_sync.py --summary  # counts only, no word lists
"""

import argparse
import json
import sys
import tomllib
from io import StringIO
from pathlib import Path

import mysql.connector
import paramiko
from sshtunnel import SSHTunnelForwarder

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNC_STATE_FILE = Path.home() / ".miolingo" / "last_sync.json"


# ---------------------------------------------------------------------------
# Connections (copied from sync_db.py for standalone use)
# ---------------------------------------------------------------------------

def _load_secrets() -> dict:
    for p in [PROJECT_ROOT / ".streamlit" / "secrets.toml", Path(".streamlit/secrets.toml")]:
        if p.exists():
            with open(p, "rb") as f:
                return tomllib.load(f)
    sys.exit("Cannot find .streamlit/secrets.toml")


def open_local(secrets: dict) -> mysql.connector.MySQLConnection:
    cfg = secrets["local_db"]
    sock = cfg.get("unix_socket", "")
    if sock:
        return mysql.connector.connect(
            unix_socket=sock, database=cfg["database"],
            user=cfg["user"], password=cfg["password"])
    return mysql.connector.connect(
        host=cfg["host"], port=int(cfg.get("port", 3306)),
        database=cfg["database"], user=cfg["user"], password=cfg["password"])


def open_remote(secrets: dict):
    ssh = secrets["ssh"]; db = secrets["mysql"]
    key_file = StringIO(ssh["key_content"])
    skey = None
    for kls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            key_file.seek(0); skey = kls.from_private_key(key_file); break
        except Exception:
            pass
    if skey is None:
        sys.exit("Could not parse SSH key")
    tunnel = SSHTunnelForwarder(
        (ssh["host"], int(ssh["port"])), ssh_username=ssh["username"],
        ssh_pkey=skey, remote_bind_address=("127.0.0.1", 3306), set_keepalive=30)
    tunnel.start()
    conn = mysql.connector.connect(
        host="127.0.0.1", port=tunnel.local_bind_port,
        database=db["database"], user=db["user"], password=db["password"])
    return tunnel, conn


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_sync_tables_registration():
    """Verify vocab_entries is listed in sync_db.py SYNC_TABLES."""
    sync_script = PROJECT_ROOT / "scripts" / "sync_db.py"
    content = sync_script.read_text()
    registered = "vocab_entries" in content and "upsert_vocab" in content
    if registered:
        print("✅  sync_db.py: vocab_entries registered with upsert_vocab strategy")
    else:
        print("❌  sync_db.py: vocab_entries NOT registered — run the fix!")
    return registered


def check_last_sync():
    if SYNC_STATE_FILE.exists():
        state = json.loads(SYNC_STATE_FILE.read_text())
        ts = state.get("last_sync_ts", "never")
        tables = state.get("last_sync_tables", [])
        vocab_synced = "vocab_entries" in tables
        print(f"{'✅' if vocab_synced else '⚠️ '}  Last sync: {ts}")
        if not vocab_synced:
            print(f"   ⚠️  vocab_entries was NOT in last synced tables: {tables}")
    else:
        print("⚠️   No sync state file found — sync has never run")


def fetch_vocab(conn, label: str) -> dict:
    """Returns {(user_id, language_code, word): row_dict}."""
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT user_id, language_code, word, display_word, "
        "translation, ipa, times_seen, first_seen_at, last_seen_at "
        "FROM vocab_entries ORDER BY user_id, language_code, word"
    )
    rows = cur.fetchall()
    cur.close()
    return {(r["user_id"], r["language_code"], r["word"]): r for r in rows}


def summarise_counts(data: dict, label: str):
    from collections import Counter
    counts = Counter((k[0], k[1]) for k in data)
    total = sum(counts.values())
    print(f"\n  {label}: {total} total entries")
    for (uid, lang), n in sorted(counts.items()):
        print(f"    user_id={uid} lang={lang}: {n}")


def diff_vocab(local: dict, remote: dict, summary_only: bool):
    local_only = set(local) - set(remote)
    remote_only = set(remote) - set(local)
    both = set(local) & set(remote)

    print(f"\n  Diff:")
    print(f"    Local only  : {len(local_only)}")
    print(f"    Remote only : {len(remote_only)}")
    print(f"    Both sides  : {len(both)}")

    if not summary_only:
        if local_only:
            print(f"\n  Words in LOCAL but not REMOTE (first 30):")
            for k in sorted(local_only)[:30]:
                r = local[k]
                print(f"    [{k[0]}] {k[1]}: {r['display_word']!r}  (seen {r['times_seen']}x)")
        if remote_only:
            print(f"\n  Words in REMOTE but not LOCAL (first 30):")
            for k in sorted(remote_only)[:30]:
                r = remote[k]
                print(f"    [{k[0]}] {k[1]}: {r['display_word']!r}  (seen {r['times_seen']}x)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true", help="Counts only, no word lists")
    args = parser.parse_args()

    secrets = _load_secrets()

    print("=" * 60)
    print("  Miolingo vocab_entries sync diagnostic")
    print("=" * 60)

    check_sync_tables_registration()
    check_last_sync()

    print("\nConnecting to databases...")
    lconn = open_local(secrets)
    tunnel, rconn = open_remote(secrets)

    try:
        local = fetch_vocab(lconn, "LOCAL")
        remote = fetch_vocab(rconn, "REMOTE")
    finally:
        lconn.close()
        rconn.close()
        tunnel.stop()

    summarise_counts(local, "LOCAL")
    summarise_counts(remote, "REMOTE")
    diff_vocab(local, remote, args.summary)

    local_only = set(local) - set(remote)
    remote_only = set(remote) - set(local)

    print("\n" + "=" * 60)
    if local_only or remote_only:
        print(f"  ❌  OUT OF SYNC: {len(local_only)} local-only, {len(remote_only)} remote-only")
        print("  Run: python scripts/sync_db.py --full")
    else:
        print("  ✅  IN SYNC: both sides have identical vocab_entries keys")
    print("=" * 60)


if __name__ == "__main__":
    main()
