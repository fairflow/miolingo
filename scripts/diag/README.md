# scripts/diag/

Standalone read-only diagnostic CLI scripts. Each connects to local *or*
remote (via `local_db.enabled` in `secrets.toml`) and prints results to
stdout — none of them write. Most have been superseded by tabs in the
unified admin app, but they remain useful when:

- Streamlit is down and you need a quick sanity check from a terminal.
- You want the *raw* / unfiltered view (e.g. version-cosmetic schema
  noise) that the admin tab deliberately hides.

Run with the venv python directly:

```
venv/bin/python3 scripts/diag/diag_schema_compare.py
```

| Script | Purpose | Admin-tab equivalent |
|---|---|---|
| `diag_vocab_keys.py` | Show the unique-key columns on `vocab_entries` plus per-user × language × source_language row counts. Was the smoking gun for the (fr,en)≠(pt,en) bug. | DB Health → row counts + Users → per-user audit |
| `diag_user_auth.py` | List every user with role / active flag / argon2id hash prefix. Searches case-insensitively for "digby" and prints the full hash. | Users tab |
| `diag_schema_compare.py` | Full schema dump of both DBs and the **unfiltered** column-by-column diff (every `int` vs `int(11)`, every `NULL` default, etc.). Useful for inspecting the cosmetic filter itself. | DB Health → schema diff (filtered) |

Delete any of these if they go stale or unused — they hold no
unique state.
