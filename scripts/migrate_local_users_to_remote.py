#!/usr/bin/env python3
"""Migrate users that exist in local DB but not in remote DB.

Reads both DBs, finds users present locally but absent remotely (by user_id),
and INSERTs them into remote preserving the original user_id. Safe to re-run
(skips users already present on remote).
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import tomllib
secrets = tomllib.loads((ROOT / ".streamlit/secrets.toml").read_text())

import mysql.connector

local_cfg = secrets["local_db"]
local = mysql.connector.connect(
    unix_socket=local_cfg["unix_socket"],
    database=local_cfg["database"],
    user=local_cfg["user"],
    password=local_cfg["password"],
)

from sync_db import open_remote_connection
tunnel, remote = open_remote_connection(secrets)

lc = local.cursor(dictionary=True)
rc = remote.cursor(dictionary=True)

# Fetch all user_ids already in remote
rc.execute("SELECT user_id FROM users")
remote_ids = {row["user_id"] for row in rc.fetchall()}

# Fetch all users from local
lc.execute(
    "SELECT user_id, username, email, password_hash, created_at, last_login, "
    "email_verified, is_active, role FROM users ORDER BY user_id"
)
local_users = lc.fetchall()

missing = [u for u in local_users if u["user_id"] not in remote_ids]

if not missing:
    print("No missing users — remote is already up to date.")
else:
    print(f"Found {len(missing)} user(s) in local but not in remote:")
    for u in missing:
        print(f"  id={u['user_id']:3d}  {u['username']!r:25s}  {u['email']!r}")

    confirm = input("\nInsert these into remote? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
    else:
        rc2 = remote.cursor()
        for u in missing:
            rc2.execute(
                """
                INSERT INTO users
                  (user_id, username, email, password_hash, created_at, last_login,
                   email_verified, is_active, role)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE user_id=user_id
                """,
                (
                    u["user_id"], u["username"], u["email"], u["password_hash"],
                    u["created_at"], u["last_login"],
                    u["email_verified"], u["is_active"], u["role"],
                ),
            )
            print(f"  Inserted user_id={u['user_id']} ({u['username']!r})")
        remote.commit()
        print(f"\nDone — {len(missing)} user(s) migrated to remote.")

local.close()
remote.close()
tunnel.stop()
