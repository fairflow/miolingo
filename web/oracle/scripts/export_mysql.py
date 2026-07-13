#!/usr/bin/env python3
"""One-off MySQL → miolingo-export.json (the web app's import format).

Exports a user's vocab_entries + user_progress so the browser app can import
them (Vocabulary tab → Import JSON). Runs against the local mirror by default
(same connection pattern as scripts/apply_sql.py); use --target remote to go
through the SSH tunnel.

Usage:
    venv/bin/python web/oracle/scripts/export_mysql.py --email matthew@... \
        [--target local|remote] [--lang pt] [-o miolingo-export.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def _load_secrets() -> dict:
    import tomllib

    path = REPO / ".streamlit" / "secrets.toml"
    if not path.exists():
        raise SystemExit(f"secrets not found: {path}")
    return tomllib.loads(path.read_text())


def _connect(target: str, secrets: dict):
    import mysql.connector

    if target == "remote":
        from sync_db import open_remote_connection

        tunnel, conn = open_remote_connection(secrets)
        return tunnel, conn
    db = secrets.get("local_db") or secrets["mysql_local"]
    kwargs = dict(user=db["user"], password=db["password"],
                  database=db["database"])
    if db.get("unix_socket"):
        kwargs["unix_socket"] = db["unix_socket"]
    else:
        kwargs.update(host=db.get("host", "127.0.0.1"), port=int(db.get("port", 3306)))
    return None, mysql.connector.connect(**kwargs)


def _iso(x) -> str:
    if isinstance(x, datetime):
        return x.isoformat()
    return str(x) if x else "1970-01-01T00:00:00"


def export_user(conn, email: str, lang: str | None) -> dict:
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id FROM users WHERE email=%s OR username=%s", (email, email))
    user = cur.fetchone()
    if user is None:
        raise SystemExit(f"no user found for {email!r}")
    uid = user["id"]

    lang_clause = " AND language_code=%s" if lang else ""
    lang_args = (lang,) if lang else ()

    cur.execute(
        f"SELECT * FROM vocab_entries WHERE user_id=%s{lang_clause}", (uid, *lang_args)
    )
    vocab = []
    for seq, r in enumerate(cur.fetchall(), start=1):
        word = (r.get("word") or "").lower()
        if not word:
            continue
        vocab.append({
            "lang": r["language_code"],
            "word": word,
            "displayWord": r.get("display_word") or r.get("word") or word,
            "translation": r.get("translation"),
            "ipa": r.get("ipa"),
            "sourceName": r.get("source"),
            "url": r.get("url"),
            "contextBefore": r.get("context_before"),
            "contextLine": r.get("context_line"),
            "contextAfter": r.get("context_after"),
            "timesSeen": int(r.get("times_seen") or 1),
            "firstSeq": seq,  # logical clock synthesized from row order
            "lastSeq": seq,
            "notes": r.get("notes"),
            "firstSeenAt": _iso(r.get("first_seen_at")),
            "lastSeenAt": _iso(r.get("last_seen_at")),
        })

    cur.execute(
        f"SELECT * FROM user_progress WHERE user_id=%s{lang_clause} ORDER BY practice_date",
        (uid, *lang_args),
    )
    log = []
    for r in cur.fetchall():
        sim = float(r.get("similarity_score") or 0)
        if sim > 1.5:  # stored as percent in MySQL; the web app uses 0..1
            sim /= 100.0
        log.append({
            "lang": r["language_code"],
            "date": _iso(r.get("practice_date")),
            "target": r.get("target_phrase") or "",
            "recognized": r.get("recognized_phrase") or "",
            "targetIpa": r.get("target_phonemes") or "",
            "algorithm": "edit_distance",  # legacy rows predate weighted_phone
            "compIpa": r.get("user_phonemes") or "",
            "compSimilarity": sim,
            "accIpa": "",
            "accSimilarity": None,
            "perfect": bool(r.get("perfect_match")),
            "similarity": sim,
            "origin": "quick",
        })

    return {
        "miolingo_export": 1,
        "exportedAt": datetime.now().astimezone().isoformat(),
        "vocab": vocab,
        "practiceLog": log,
        "settings": {},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", required=True, help="user email or username")
    ap.add_argument("--target", choices=("local", "remote"), default="local")
    ap.add_argument("--lang", help="restrict to one language_code")
    ap.add_argument("-o", "--out", type=Path, default=Path("miolingo-export.json"))
    args = ap.parse_args()

    tunnel, conn = _connect(args.target, _load_secrets())
    try:
        data = export_user(conn, args.email, args.lang)
    finally:
        conn.close()
        if tunnel is not None:
            tunnel.stop()

    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    print(f"wrote {args.out}: {len(data['vocab'])} vocab, "
          f"{len(data['practiceLog'])} log rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
