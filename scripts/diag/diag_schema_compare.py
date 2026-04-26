#!/usr/bin/env python3
"""Deep comparison of local vs remote DB schema.

Reports: tables, columns (type/nullable/default), indexes, foreign keys,
and any differences between the two databases.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import tomllib
secrets = tomllib.loads((ROOT / ".streamlit/secrets.toml").read_text())

import mysql.connector

# ── Connect to both ──────────────────────────────────────────────────────────
local_cfg = secrets["local_db"]
local = mysql.connector.connect(
    unix_socket=local_cfg["unix_socket"],
    database=local_cfg["database"],
    user=local_cfg["user"],
    password=local_cfg["password"],
)
print("LOCAL  connected")

from sync_db import open_remote_connection
tunnel, remote = open_remote_connection(secrets)
print("REMOTE connected\n")

def get_schema(conn, db_name):
    """Return a nested dict describing every table in the database."""
    c = conn.cursor(dictionary=True)
    schema = {}

    # Tables
    c.execute(f"SELECT TABLE_NAME, TABLE_ROWS, ENGINE, TABLE_COMMENT "
              f"FROM information_schema.TABLES "
              f"WHERE TABLE_SCHEMA = '{db_name}' ORDER BY TABLE_NAME")
    tables = {r["TABLE_NAME"]: r for r in c.fetchall()}

    for tbl in sorted(tables):
        schema[tbl] = {"columns": {}, "indexes": {}, "foreign_keys": {}}

        # Columns
        c.execute(
            "SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_DEFAULT, IS_NULLABLE, "
            "COLUMN_TYPE, COLUMN_KEY, EXTRA, COLUMN_COMMENT "
            "FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA='{db_name}' AND TABLE_NAME='{tbl}' "
            "ORDER BY ORDINAL_POSITION"
        )
        for row in c.fetchall():
            schema[tbl]["columns"][row["COLUMN_NAME"]] = {
                "pos":      row["ORDINAL_POSITION"],
                "type":     row["COLUMN_TYPE"],
                "nullable": row["IS_NULLABLE"],
                "default":  row["COLUMN_DEFAULT"],
                "key":      row["COLUMN_KEY"],
                "extra":    row["EXTRA"],
            }

        # Indexes
        c.execute(
            "SELECT INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, NON_UNIQUE, NULLABLE "
            "FROM information_schema.STATISTICS "
            f"WHERE TABLE_SCHEMA='{db_name}' AND TABLE_NAME='{tbl}' "
            "ORDER BY INDEX_NAME, SEQ_IN_INDEX"
        )
        idx = defaultdict(list)
        for row in c.fetchall():
            idx[row["INDEX_NAME"]].append({
                "col": row["COLUMN_NAME"],
                "seq": row["SEQ_IN_INDEX"],
                "unique": row["NON_UNIQUE"] == 0,
                "nullable": row["NULLABLE"],
            })
        schema[tbl]["indexes"] = dict(idx)

        # Foreign keys
        c.execute(
            "SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, "
            "REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            f"WHERE TABLE_SCHEMA='{db_name}' AND TABLE_NAME='{tbl}' "
            "AND REFERENCED_TABLE_NAME IS NOT NULL "
            "ORDER BY CONSTRAINT_NAME"
        )
        for row in c.fetchall():
            schema[tbl]["foreign_keys"][row["CONSTRAINT_NAME"]] = {
                "col": row["COLUMN_NAME"],
                "ref_table": row["REFERENCED_TABLE_NAME"],
                "ref_col": row["REFERENCED_COLUMN_NAME"],
            }

    return schema

LOCAL_DB  = local_cfg["database"]
REMOTE_DB = secrets["mysql"]["database"]

print(f"Fetching LOCAL  schema  ({LOCAL_DB})…")
local_schema = get_schema(local, LOCAL_DB)
print(f"Fetching REMOTE schema  ({REMOTE_DB})…\n")
remote_schema = get_schema(remote, REMOTE_DB)

# ── Print full schemas ────────────────────────────────────────────────────────
def print_schema(label, schema):
    print(f"\n{'='*72}")
    print(f"  {label}  —  {len(schema)} tables")
    print(f"{'='*72}")
    for tbl, info in sorted(schema.items()):
        print(f"\n  TABLE: {tbl}")
        print(f"    Columns:")
        for col, d in info["columns"].items():
            nullable = "NULL" if d["nullable"] == "YES" else "NOT NULL"
            default  = f" DEFAULT {d['default']!r}" if d["default"] is not None else ""
            extra    = f" {d['extra']}" if d["extra"] else ""
            key      = f" [{d['key']}]" if d["key"] else ""
            print(f"      {col:35s} {d['type']:30s} {nullable}{default}{extra}{key}")
        print(f"    Indexes:")
        for idx_name, cols in info["indexes"].items():
            unique = "UNIQUE" if cols[0]["unique"] else "INDEX"
            col_list = ", ".join(c["col"] for c in cols)
            print(f"      {unique:8s} {idx_name:35s} ({col_list})")
        if info["foreign_keys"]:
            print(f"    Foreign keys:")
            for fk_name, fk in info["foreign_keys"].items():
                print(f"      {fk_name}: {fk['col']} → {fk['ref_table']}.{fk['ref_col']}")

print_schema(f"LOCAL  ({LOCAL_DB})",  local_schema)
print_schema(f"REMOTE ({REMOTE_DB})", remote_schema)

# ── Diff ──────────────────────────────────────────────────────────────────────
print(f"\n\n{'='*72}")
print("  DIFF  (LOCAL vs REMOTE)")
print(f"{'='*72}")

all_tables = sorted(set(local_schema) | set(remote_schema))
diffs_found = False

for tbl in all_tables:
    in_local  = tbl in local_schema
    in_remote = tbl in remote_schema

    if not in_local:
        print(f"\n  [TABLE MISSING IN LOCAL]  {tbl}")
        diffs_found = True
        continue
    if not in_remote:
        print(f"\n  [TABLE MISSING IN REMOTE] {tbl}")
        diffs_found = True
        continue

    L = local_schema[tbl]
    R = remote_schema[tbl]
    tbl_diffs = []

    # Columns
    all_cols = sorted(set(L["columns"]) | set(R["columns"]))
    for col in all_cols:
        if col not in L["columns"]:
            tbl_diffs.append(f"    [COL MISSING IN LOCAL]  {col}")
        elif col not in R["columns"]:
            tbl_diffs.append(f"    [COL MISSING IN REMOTE] {col}")
        else:
            lc, rc = L["columns"][col], R["columns"][col]
            for field in ("type", "nullable", "default", "extra"):
                if lc[field] != rc[field]:
                    tbl_diffs.append(f"    [COL DIFF] {col}.{field}: LOCAL={lc[field]!r}  REMOTE={rc[field]!r}")

    # Indexes
    all_idx = sorted(set(L["indexes"]) | set(R["indexes"]))
    for idx in all_idx:
        if idx not in L["indexes"]:
            cols = ", ".join(c["col"] for c in R["indexes"][idx])
            tbl_diffs.append(f"    [IDX MISSING IN LOCAL]  {idx} ({cols})")
        elif idx not in R["indexes"]:
            cols = ", ".join(c["col"] for c in L["indexes"][idx])
            tbl_diffs.append(f"    [IDX MISSING IN REMOTE] {idx} ({cols})")
        else:
            l_cols = [c["col"] for c in L["indexes"][idx]]
            r_cols = [c["col"] for c in R["indexes"][idx]]
            if l_cols != r_cols:
                tbl_diffs.append(f"    [IDX DIFF] {idx}: LOCAL=({', '.join(l_cols)})  REMOTE=({', '.join(r_cols)})")

    if tbl_diffs:
        print(f"\n  TABLE: {tbl}")
        for d in tbl_diffs:
            print(d)
        diffs_found = True

if not diffs_found:
    print("\n  Schemas are identical.")

# ── Row counts ────────────────────────────────────────────────────────────────
print(f"\n\n{'='*72}")
print("  ROW COUNTS")
print(f"{'='*72}")
print(f"  {'Table':35s}  {'Local':>10s}  {'Remote':>10s}")
print(f"  {'-'*35}  {'-'*10}  {'-'*10}")
lc2 = local.cursor()
rc2 = remote.cursor()
for tbl in sorted(set(local_schema) | set(remote_schema)):
    try:
        lc2.execute(f"SELECT COUNT(*) FROM `{tbl}`")
        l_cnt = lc2.fetchone()[0]
    except Exception:
        l_cnt = "N/A"
    try:
        rc2.execute(f"SELECT COUNT(*) FROM `{tbl}`")
        r_cnt = rc2.fetchone()[0]
    except Exception:
        r_cnt = "N/A"
    marker = "  <<<" if l_cnt != r_cnt else ""
    print(f"  {tbl:35s}  {str(l_cnt):>10s}  {str(r_cnt):>10s}{marker}")

local.close()
remote.close()
tunnel.stop()
print("\nDone.")
