#!/usr/bin/env python3
"""Diagnose a user account: existence, password hash, and auth algorithm."""
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
    print(">> Using LOCAL MySQL")
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

cur = conn.cursor(dictionary=True)

print("\n=== All users ===")
cur.execute(
    "SELECT user_id, username, email, password_hash, is_active, role "
    "FROM users ORDER BY user_id"
)
for row in cur.fetchall():
    print(f"  id={row['user_id']:3d}  username={row['username']!r:20s}  "
          f"email={row['email']!r:35s}  active={row['is_active']}  role={row['role']!r}  "
          f"hash_prefix={row['password_hash'][:30] if row['password_hash'] else 'NULL'}...")

print("\n=== Looking for 'digby' (case-insensitive) ===")
cur.execute(
    "SELECT user_id, username, email, password_hash, is_active "
    "FROM users "
    "WHERE LOWER(username) LIKE '%digby%' OR LOWER(email) LIKE '%digby%'"
)
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"  FOUND: id={row['user_id']}  username={row['username']!r}  "
              f"email={row['email']!r}  active={row['is_active']}")
        print(f"  full hash: {row['password_hash']}")
else:
    print("  (no match)")

conn.close()
if tunnel:
    tunnel.stop()
