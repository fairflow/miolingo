#!/usr/bin/env python3
"""Smoke-test admin_sync.sync_table end-to-end (LOCAL → REMOTE).

Runs preview + sync for each whitelisted table with policy='skip'. Used
to verify the unread-result fix and the new user_progress path; safe to
re-run because skip policy never overwrites existing rows.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

# admin_sync uses st.secrets indirectly via app_mysql; satisfy it here.
import streamlit as st
import tomllib
secrets = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text())
for k, v in secrets.items():
    st._secrets = getattr(st, "_secrets", {})  # noqa
# easier path: monkey-patch st.secrets via load
class _SecretsShim(dict):
    def get(self, key, default=None):
        return super().get(key, default)
st.secrets = _SecretsShim(secrets)  # type: ignore[attr-defined]

import admin_sync

print(f"Tables: {list(admin_sync.SYNCABLE_TABLES)}\n")

for table in admin_sync.SYNCABLE_TABLES:
    print(f"=== {table} ===")
    try:
        prev = admin_sync.preview(table, source="local", target="remote")
        print(f"  preview: {prev}")
    except Exception as e:
        print(f"  preview FAILED: {e}")
        continue
    try:
        result = admin_sync.sync_table(
            table, source="local", target="remote", policy="skip"
        )
        print(f"  sync:    {result}")
    except Exception as e:
        print(f"  sync FAILED: {type(e).__name__}: {e}")
    print()
