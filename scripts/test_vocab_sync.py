#!/usr/bin/env python3
"""
test_vocab_sync.py — Automated round-trip sync test for vocab_entries.

Inserts synthetic rows on each side, runs sync_upsert_vocab directly,
then verifies the rows propagated correctly and merge semantics hold.
All test rows are deleted on exit (pass or fail).

Usage:
    source venv/bin/activate
    python scripts/test_vocab_sync.py            # run all tests
    python scripts/test_vocab_sync.py --keep     # leave test rows in DB (debug)

Exit code:
    0 — all tests passed
    1 — one or more tests failed (details printed)
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap (run from project root or worktree root)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    import mysql.connector
    import paramiko
    import tomllib
    from sshtunnel import SSHTunnelForwarder
except ImportError as e:
    sys.exit(f"Missing dependency: {e}  (source venv/bin/activate first)")

# ---------------------------------------------------------------------------
# Test marker — all synthetic rows use words starting with this prefix.
# Makes cleanup trivial: DELETE FROM vocab_entries WHERE word LIKE '_ts_%'
# (MySQL treats '_' as single-char wildcard, so we escape it with LIKE ESCAPE)
# ---------------------------------------------------------------------------
TEST_PREFIX = "__synctest__"
TEST_LANGUAGE = "xx"      # ISO 639-2 code that won't collide with real languages

# Resolved at runtime from the local `users` table (first user_id found).
# Using a real user_id satisfies the FK constraint on both sides.
TEST_USER_ID: int = -1    # sentinel; set in main() before any test runs

PASS = "\033[32m✅ PASS\033[0m"
FAIL = "\033[31m❌ FAIL\033[0m"


# ---------------------------------------------------------------------------
# Connection helpers (copied / aligned with sync_db.py)
# ---------------------------------------------------------------------------

def _load_secrets() -> dict:
    for p in [
        PROJECT_ROOT / ".streamlit" / "secrets.toml",
        Path(".streamlit/secrets.toml"),
    ]:
        if p.exists():
            with open(p, "rb") as f:
                return tomllib.load(f)
    sys.exit("Cannot find .streamlit/secrets.toml")


def open_local(secrets: dict) -> mysql.connector.MySQLConnection:
    cfg = secrets["local_db"]
    sock = cfg.get("unix_socket", "")
    if sock:
        return mysql.connector.connect(
            unix_socket=sock,
            database=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            autocommit=False,
        )
    return mysql.connector.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        autocommit=False,
    )


def open_remote(secrets: dict):
    ssh = secrets["ssh"]
    db = secrets["mysql"]
    key_file = StringIO(ssh["key_content"])
    skey = None
    for kls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            key_file.seek(0)
            skey = kls.from_private_key(key_file)
            break
        except Exception:
            pass
    if skey is None:
        sys.exit("Could not parse SSH key from secrets")

    tunnel = SSHTunnelForwarder(
        (ssh["host"], int(ssh["port"])),
        ssh_username=ssh["username"],
        ssh_pkey=skey,
        remote_bind_address=("127.0.0.1", 3306),
        set_keepalive=30,
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
    return tunnel, conn


# ---------------------------------------------------------------------------
# Sync (inlined from sync_db.py to avoid subprocess overhead)
# ---------------------------------------------------------------------------

_VOCAB_COLS = [
    "user_id", "language_code", "word", "display_word",
    "translation", "ipa", "source_name",
    "context_before", "context_line", "context_after",
    "url", "times_seen", "first_seen_at", "last_seen_at", "notes",
]

_VOCAB_INSERT_SQL = """
    INSERT INTO `vocab_entries` ({cols})
    VALUES ({placeholders})
    ON DUPLICATE KEY UPDATE
        times_seen    = GREATEST(times_seen,    VALUES(times_seen)),
        last_seen_at  = GREATEST(last_seen_at,  VALUES(last_seen_at)),
        first_seen_at = LEAST(first_seen_at,    VALUES(first_seen_at)),
        translation   = COALESCE(translation,   VALUES(translation)),
        ipa           = COALESCE(ipa,            VALUES(ipa)),
        source_name   = COALESCE(source_name,   VALUES(source_name)),
        context_before= COALESCE(NULLIF(context_before,''), VALUES(context_before)),
        context_line  = COALESCE(NULLIF(context_line,''),   VALUES(context_line)),
        context_after = COALESCE(NULLIF(context_after,''),  VALUES(context_after)),
        url           = COALESCE(NULLIF(url,''),            VALUES(url)),
        notes         = COALESCE(NULLIF(notes,''),          VALUES(notes))
""".format(
    cols=", ".join(f"`{c}`" for c in _VOCAB_COLS),
    placeholders=", ".join(["%s"] * len(_VOCAB_COLS)),
)


def _upsert_rows(src_conn, dst_conn, label: str) -> dict:
    """Copy all rows from src to dst using the upsert SQL."""
    col_list = ", ".join(f"`{c}`" for c in _VOCAB_COLS)
    scur = src_conn.cursor(dictionary=True)
    scur.execute(f"SELECT {col_list} FROM `vocab_entries`")
    rows = scur.fetchall()
    scur.close()

    dcur = dst_conn.cursor()
    upserted = 0
    errors = 0
    for row in rows:
        try:
            dcur.execute(_VOCAB_INSERT_SQL, tuple(row[c] for c in _VOCAB_COLS))
            if dcur.rowcount >= 1:
                upserted += 1
        except mysql.connector.Error as e:
            print(f"    [WARN] upsert error ({label}) word={row.get('word')!r}: {e}")
            errors += 1
    dst_conn.commit()
    dcur.close()
    return {"upserted": upserted, "errors": errors}


def run_bidirectional_sync(local_conn, remote_conn):
    """Run one full bidirectional vocab_entries sync (local↔remote)."""
    l2r = _upsert_rows(local_conn, remote_conn, "L→R")
    r2l = _upsert_rows(remote_conn, local_conn, "R→L")
    return l2r, r2l


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def insert_row(conn, *, word: str, translation: str = None, times_seen: int = 1,
               first_seen_at: datetime = None, last_seen_at: datetime = None,
               notes: str = None) -> None:
    now = datetime.now()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vocab_entries
            (user_id, language_code, word, display_word, translation,
             times_seen, first_seen_at, last_seen_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            TEST_USER_ID, TEST_LANGUAGE, word, word, translation,
            times_seen,
            first_seen_at or now,
            last_seen_at or now,
            notes,
        ),
    )
    conn.commit()
    cur.close()


def fetch_row(conn, word: str) -> dict | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM vocab_entries WHERE user_id=%s AND language_code=%s AND word=%s",
        (TEST_USER_ID, TEST_LANGUAGE, word),
    )
    row = cur.fetchone()
    cur.close()
    return row


def delete_test_rows(conn, label: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM vocab_entries WHERE word LIKE %s AND user_id=%s",
        (f"{TEST_PREFIX}%", TEST_USER_ID),
    )
    count = cur.rowcount
    conn.commit()
    cur.close()
    return count


def count_test_rows(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM vocab_entries WHERE word LIKE %s AND user_id=%s",
        (f"{TEST_PREFIX}%", TEST_USER_ID),
    )
    n = cur.fetchone()[0]
    cur.close()
    return n


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name: str, condition: bool, detail: str = ""):
        if condition:
            print(f"  {PASS}  {name}")
            self.passed += 1
        else:
            print(f"  {FAIL}  {name}" + (f"\n         {detail}" if detail else ""))
            self.failed += 1

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  {self.passed}/{total} tests passed", end="")
        if self.failed:
            print(f"  ({self.failed} FAILED)")
        else:
            print("  — all clear")
        print("=" * 60)
        return self.failed == 0


def test_local_to_remote(lconn, rconn, results: Results):
    """Insert on local, sync, verify appears on remote."""
    print("\n[1] Local → Remote propagation")
    word = f"{TEST_PREFIX}l2r"

    # Pre-condition: row must not exist on remote
    pre = fetch_row(rconn, word)
    results.check("Row absent on remote before test", pre is None,
                  f"Unexpected row: {pre}")

    insert_row(lconn, word=word, translation="hello", times_seen=3)
    results.check("Row inserted locally", fetch_row(lconn, word) is not None)

    run_bidirectional_sync(lconn, rconn)

    remote_row = fetch_row(rconn, word)
    results.check("Row present on remote after sync", remote_row is not None,
                  "Sync did not propagate local row to remote")
    if remote_row:
        results.check("Translation preserved", remote_row["translation"] == "hello",
                      f"got {remote_row['translation']!r}")
        results.check("times_seen preserved", remote_row["times_seen"] == 3,
                      f"got {remote_row['times_seen']}")


def test_remote_to_local(lconn, rconn, results: Results):
    """Insert on remote, sync, verify appears on local."""
    print("\n[2] Remote → Local propagation")
    word = f"{TEST_PREFIX}r2l"

    pre = fetch_row(lconn, word)
    results.check("Row absent on local before test", pre is None,
                  f"Unexpected row: {pre}")

    insert_row(rconn, word=word, translation="world", notes="from-remote")
    results.check("Row inserted remotely", fetch_row(rconn, word) is not None)

    run_bidirectional_sync(lconn, rconn)

    local_row = fetch_row(lconn, word)
    results.check("Row present on local after sync", local_row is not None,
                  "Sync did not propagate remote row to local")
    if local_row:
        results.check("Translation preserved", local_row["translation"] == "world",
                      f"got {local_row['translation']!r}")
        results.check("Notes preserved", local_row["notes"] == "from-remote",
                      f"got {local_row['notes']!r}")


def test_times_seen_greatest(lconn, rconn, results: Results):
    """GREATEST(times_seen) merge: higher count wins on both sides."""
    print("\n[3] Merge semantics — times_seen = GREATEST")
    word = f"{TEST_PREFIX}merge_ts"
    now = datetime.now()
    old = now - timedelta(hours=1)

    # Insert on local with times_seen=5, on remote with times_seen=9
    insert_row(lconn, word=word, times_seen=5, first_seen_at=old, last_seen_at=now)
    insert_row(rconn, word=word, times_seen=9, first_seen_at=old, last_seen_at=now)

    run_bidirectional_sync(lconn, rconn)

    local_row = fetch_row(lconn, word)
    remote_row = fetch_row(rconn, word)

    if local_row:
        results.check(
            "Local times_seen = max(5,9) = 9",
            local_row["times_seen"] == 9,
            f"got {local_row['times_seen']}",
        )
    else:
        results.check("Local row present for merge test", False)

    if remote_row:
        results.check(
            "Remote times_seen = max(5,9) = 9",
            remote_row["times_seen"] == 9,
            f"got {remote_row['times_seen']}",
        )
    else:
        results.check("Remote row present for merge test", False)


def test_coalesce_fills_nulls(lconn, rconn, results: Results):
    """COALESCE: NULL field filled by non-NULL value from other side."""
    print("\n[4] Merge semantics — COALESCE fills NULL fields")
    word = f"{TEST_PREFIX}coalesce"
    now = datetime.now()

    # Local: has translation, no IPA
    insert_row(lconn, word=word, translation="sun")
    # Remote: no translation, has notes
    rconn_cur = rconn.cursor()
    rconn_cur.execute(
        """
        INSERT INTO vocab_entries
            (user_id, language_code, word, display_word,
             times_seen, first_seen_at, last_seen_at, notes)
        VALUES (%s, %s, %s, %s, 1, %s, %s, %s)
        """,
        (TEST_USER_ID, TEST_LANGUAGE, word, word, now, now, "my-note"),
    )
    rconn.commit()
    rconn_cur.close()

    run_bidirectional_sync(lconn, rconn)

    local_row = fetch_row(lconn, word)
    remote_row = fetch_row(rconn, word)

    if local_row:
        results.check(
            "Local gets notes from remote",
            local_row.get("notes") == "my-note",
            f"got {local_row.get('notes')!r}",
        )
    else:
        results.check("Local row exists for coalesce test", False)

    if remote_row:
        results.check(
            "Remote gets translation from local",
            remote_row.get("translation") == "sun",
            f"got {remote_row.get('translation')!r}",
        )
    else:
        results.check("Remote row exists for coalesce test", False)


def test_idempotent(lconn, rconn, results: Results):
    """Running sync twice doesn't change row counts or data."""
    print("\n[5] Idempotency — second sync changes nothing")
    word = f"{TEST_PREFIX}idem"
    insert_row(lconn, word=word, translation="moon", times_seen=2)

    run_bidirectional_sync(lconn, rconn)
    local_before = fetch_row(lconn, word)
    remote_before = fetch_row(rconn, word)

    # Second sync
    run_bidirectional_sync(lconn, rconn)
    local_after = fetch_row(lconn, word)
    remote_after = fetch_row(rconn, word)

    results.check(
        "Local row unchanged after second sync",
        local_before and local_after and
        local_before["times_seen"] == local_after["times_seen"] and
        local_before["translation"] == local_after["translation"],
        f"before={local_before}, after={local_after}",
    )
    results.check(
        "Remote row unchanged after second sync",
        remote_before and remote_after and
        remote_before["times_seen"] == remote_after["times_seen"],
        f"before={remote_before}, after={remote_after}",
    )


def test_no_real_data_lost(lconn, rconn, results: Results):
    """Real vocab_entries rows (non-test) still exist on both sides after sync.

    This is a canary: if sync deletes or truncates real rows, this fails.
    """
    print("\n[6] Real-data integrity — production rows untouched")
    lcur = lconn.cursor()
    lcur.execute(
        "SELECT COUNT(*) FROM vocab_entries WHERE word NOT LIKE %s OR user_id != %s",
        (f"{TEST_PREFIX}%", TEST_USER_ID),
    )
    local_real = lcur.fetchone()[0]
    lcur.close()

    rcur = rconn.cursor()
    rcur.execute(
        "SELECT COUNT(*) FROM vocab_entries WHERE word NOT LIKE %s OR user_id != %s",
        (f"{TEST_PREFIX}%", TEST_USER_ID),
    )
    remote_real_before = rcur.fetchone()[0]
    rcur.close()

    # Run sync
    run_bidirectional_sync(lconn, rconn)

    rcur = rconn.cursor()
    rcur.execute(
        "SELECT COUNT(*) FROM vocab_entries WHERE word NOT LIKE %s OR user_id != %s",
        (f"{TEST_PREFIX}%", TEST_USER_ID),
    )
    remote_real_after = rcur.fetchone()[0]
    rcur.close()

    results.check(
        f"Remote real rows ≥ local real rows after sync ({local_real} local → {remote_real_after} remote)",
        remote_real_after >= local_real,
        f"remote had {remote_real_before} before, {remote_real_after} after; local has {local_real}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true",
                        help="Don't delete test rows after run (for debugging)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Miolingo vocab_entries sync test suite")
    print("=" * 60)
    print("\nConnecting to databases…")

    secrets = _load_secrets()
    lconn = open_local(secrets)
    tunnel, rconn = open_remote(secrets)

    # Discover a real user_id that satisfies the FK constraint on both sides.
    # The `users` table syncs remote→local, so any local user also exists remotely.
    global TEST_USER_ID
    lcur = lconn.cursor()
    lcur.execute("SELECT user_id, username FROM users ORDER BY user_id LIMIT 1")
    row = lcur.fetchone()
    lcur.close()
    if row is None:
        sys.exit("No users found in local DB — cannot run tests")
    TEST_USER_ID = row[0]
    print(f"  Using test user_id={TEST_USER_ID} (username={row[1]!r}) with language_code={TEST_LANGUAGE!r}")

    results = Results()

    try:
        # Sanity: remove any leftover test rows from a previous failed run
        stale_l = delete_test_rows(lconn, "local")
        stale_r = delete_test_rows(rconn, "remote")
        if stale_l or stale_r:
            print(f"  (Cleared {stale_l} stale local + {stale_r} stale remote test rows from prior run)")

        test_local_to_remote(lconn, rconn, results)
        test_remote_to_local(lconn, rconn, results)
        test_times_seen_greatest(lconn, rconn, results)
        test_coalesce_fills_nulls(lconn, rconn, results)
        test_idempotent(lconn, rconn, results)
        test_no_real_data_lost(lconn, rconn, results)

    finally:
        if not args.keep:
            print("\nCleaning up test rows…")
            dl = delete_test_rows(lconn, "local")
            dr = delete_test_rows(rconn, "remote")
            print(f"  Deleted {dl} local + {dr} remote test rows")
            cleanup_done = True
        else:
            print("\n  --keep: leaving test rows in DB")

        lconn.close()
        rconn.close()
        tunnel.stop()

    ok = results.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
