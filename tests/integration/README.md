# Integration tests

Hit a real local MySQL instance. Opt-in:

```bash
source venv/bin/activate
pytest tests/integration              # run this suite
pytest -m integration                 # same, via marker
pytest                                # default suite — integration excluded
```

## One-time setup

1. Local MySQL 8 running (MacPorts `mysql8-server`).
2. `.streamlit/secrets.toml` has a `[local_db]` block with `enabled = true`.
3. Create the test database and grant the app user access:

```sql
-- Run as a MySQL admin (root or equivalent)
CREATE DATABASE IF NOT EXISTS miolingo_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON miolingo_test.* TO 'miolingo_local'@'localhost';
FLUSH PRIVILEGES;
```

The test user is NOT granted CREATE/DROP DATABASE — the fixture only manages
tables *within* `miolingo_test`, which is intentional (production-parity
privilege model).

If `local_db.enabled` is missing, or the test DB isn't reachable, the suite
is **skipped**, not failed.

## What happens

- Session setup: create throwaway database `miolingo_test`, apply
  `schema.sql` (dumped from the live local DB with `mysqldump --no-data`).
- Per-test: fresh connection, all tables truncated after the test.
- `app_mysql.get_connection()` is monkeypatched to return the test
  connection, so product code under test routes to the test DB transparently.
- Session teardown: drop `miolingo_test`.

## Updating the schema

When real schema changes land, refresh the dump:

```bash
/opt/local/bin/mysqldump \
  --socket=/opt/local/var/run/mysql8/mysqld.sock \
  -u <local_db.user> -p<local_db.password> \
  --no-data --skip-comments --compact --skip-dump-date \
  --set-gtid-purged=OFF \
  <local_db.database> > tests/integration/schema.sql

# Strip auto-increment noise so diffs are clean:
sed -i '' -E 's/ AUTO_INCREMENT=[0-9]+//g' tests/integration/schema.sql
```
