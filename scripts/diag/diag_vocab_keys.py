#!/usr/bin/env python3
"""Diagnostic: vocab_entries breakdown by user, language, source_language."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import tomllib
secrets = tomllib.loads((ROOT / ".streamlit/secrets.toml").read_text())

import mysql.connector

local_cfg = secrets.get("local_db", {})
tunnel = None

if local_cfg.get("enabled"):
    print(">> Using LOCAL MySQL via Unix socket")
    conn = mysql.connector.connect(
        unix_socket=local_cfg["unix_socket"],
        database=local_cfg["database"],
        user=local_cfg["user"],
        password=local_cfg["password"],
    )
else:
    print(">> Using REMOTE MySQL via SSH tunnel")
    from sync_db import open_remote_connection
    tunnel, conn = open_remote_connection(secrets)

cur = conn.cursor()

print("\n=== UNIQUE KEY ===")
cur.execute("SHOW INDEX FROM vocab_entries WHERE Non_unique=0 AND Key_name != 'PRIMARY'")
for row in cur.fetchall():
    print(f"  {row[2]}: col={row[4]}, seq={row[3]}, nullable={row[9]}")

print("\n=== Per-user breakdown: (user_id, language_code, source_language_code, count) ===")
cur.execute(
    "SELECT user_id, language_code, source_language_code, COUNT(*) as cnt "
    "FROM vocab_entries "
    "GROUP BY user_id, language_code, source_language_code "
    "ORDER BY user_id, language_code, cnt DESC"
)
for row in cur.fetchall():
    print(f"  user={row[0]:3d}  lang={row[1]!r:15s}  src={str(row[2]):6s}  count={row[3]}")

print("\n=== Users table (id, username/email) ===")
try:
    cur.execute("SELECT id, username FROM users ORDER BY id")
    for row in cur.fetchall():
        print(f"  id={row[0]}  username={row[1]!r}")
except Exception as e:
    try:
        cur.execute("SELECT id, email FROM users ORDER BY id")
        for row in cur.fetchall():
            print(f"  id={row[0]}  email={row[1]!r}")
    except Exception as e2:
        print(f"  (could not read users: {e2})")

conn.close()
if tunnel:
    tunnel.stop()
