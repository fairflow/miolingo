#!/usr/bin/env python3
"""Apply a .sql file to the local or remote Miolingo MySQL.

Why this exists
---------------
Running ``mysql -u <user> -p'<password>' ... < file.sql`` directly bakes
the password into the command line, which means any Claude Code
permission pattern approved for that invocation stores the password in
``settings.json`` / ``settings.local.json``. That defeats the point of
keeping credentials in ``.streamlit/secrets.toml``.

This script reads credentials from ``secrets.toml`` at run time, so the
approved permission pattern (``Bash(venv/bin/python scripts/apply_sql.py *)``)
contains no secrets.

Usage
-----
    # Apply to local DB:
    venv/bin/python scripts/apply_sql.py --target local path/to/file.sql

    # Apply to remote DB (via SSH tunnel, same path as sync_db.py):
    venv/bin/python scripts/apply_sql.py --target remote path/to/file.sql

    # Dry-run (prints the statements without executing):
    venv/bin/python scripts/apply_sql.py --target remote --dry-run path/to/file.sql

Only executes multi-statement scripts one statement at a time (splits on
``;`` terminators at the start of a line). Transactions are not used —
DDL auto-commits in MySQL anyway — but a failure mid-file leaves the DB
partially migrated, so write idempotent migrations (``IF NOT EXISTS``,
``IF EXISTS``) where possible.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _load_secrets() -> dict:
    """Read .streamlit/secrets.toml from the main-repo root.

    Worktrees symlink their secrets file back to the main repo, so this
    resolves in both layouts.
    """
    try:
        import tomllib  # py311+
    except ImportError:
        import tomli as tomllib  # type: ignore

    # Walk up from this script: .claude/worktrees/<name>/scripts/apply_sql.py
    # or miolingo/scripts/apply_sql.py — secrets live at <repo>/.streamlit/
    # regardless.
    for candidate in (ROOT / ".streamlit" / "secrets.toml",):
        if candidate.exists():
            return tomllib.loads(candidate.read_text())
    raise SystemExit(f"Could not find .streamlit/secrets.toml under {ROOT}")


def _split_statements(sql: str) -> list[str]:
    """Split a .sql script on `;` terminators.

    Strips ``--`` line comments first, THEN splits on ``;`` so a semicolon
    inside a comment (e.g. ``-- NULL means unspecified (blah);``) doesn't
    break a statement. Naive for string-literal semicolons — good enough
    for hand-written migrations. Blank chunks are dropped.
    """
    cleaned_lines = [
        ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")
    ]
    cleaned = "\n".join(cleaned_lines)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def _connect_local(secrets: dict):
    import mysql.connector
    db = secrets["mysql_local"]
    return mysql.connector.connect(
        host=db.get("host", "127.0.0.1"),
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["database"],
        autocommit=True,
    )


def _connect_remote(secrets: dict):
    # Reuse the same helper sync_db.py uses so we open exactly one code path.
    from sync_db import open_remote_connection
    tunnel, conn = open_remote_connection(secrets)
    conn.autocommit = True
    return tunnel, conn


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sql_file", type=Path, help="Path to .sql file to apply")
    ap.add_argument("--target", choices=("local", "remote"), required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the statements without executing")
    args = ap.parse_args()

    if not args.sql_file.exists():
        print(f"error: file not found: {args.sql_file}", file=sys.stderr)
        return 2

    statements = _split_statements(args.sql_file.read_text())
    print(f"Found {len(statements)} statement(s) in {args.sql_file}")

    if args.dry_run:
        for i, s in enumerate(statements, 1):
            print(f"\n-- [{i}/{len(statements)}] --\n{s};")
        return 0

    secrets = _load_secrets()
    tunnel = None
    if args.target == "local":
        conn = _connect_local(secrets)
    else:
        tunnel, conn = _connect_remote(secrets)

    try:
        cur = conn.cursor()
        for i, s in enumerate(statements, 1):
            print(f"[{i}/{len(statements)}] executing… ", end="", flush=True)
            try:
                cur.execute(s)
                print("ok")
            except Exception as e:
                print(f"FAILED: {e}")
                return 1
        cur.close()
    finally:
        conn.close()
        if tunnel is not None:
            tunnel.stop()

    print(f"✓ Applied {args.sql_file.name} to {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
