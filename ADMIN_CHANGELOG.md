# Miolingo Admin Changelog

Changelog for the admin dashboard (`src/unified_admin.py` + `src/miolingo-admin.py`).
Versions are independent from the main app's `APP_CHANGELOG.md` and tags use the
`admin-v` prefix.

## [Unreleased]

## [1.0.2-claude-dev]

### Added
- Selective table sync (translation_cache, vocab_entries, user_settings) with skip/overwrite/merge-by-timestamp policies.
- Connection diagnostics tab: SSH tunnel/connection/session views, pool-capacity snapshot, purge stale connection rows, mark dead tunnels.
- Diagnostic CLI scripts moved to scripts/diag/ with README.

## [1.0.1-claude-dev]

### Added
- Initial unified admin entrypoint (PR-2): users CRUD with reset-password / force-logout / soft+hard delete; DB Health tab (schema diff with version-cosmetic filter, row counts, per-user audit); Migration Runner with `schema_migrations` audit log.

## [1.0.0]

### Added
- Initial admin dashboard.
