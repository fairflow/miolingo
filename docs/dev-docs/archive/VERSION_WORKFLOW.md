# Version Management & Git Workflow

## Quick Reference

<!-- VERSION MARKER - Update this when releasing new version -->
**Current Version:** 7.1.2
**App File:** `src/app.py`
**Admin File:** `src/miolingo-admin.py`
**Versioning:** Semantic Versioning (MAJOR.MINOR.PATCH)
**Git Tags:** Match versions (`v3.0.0`, `v3.1.0`, etc.)
**Repository:** `fairflow/miolingo` on GitHub
**Live App:** [miolingo3.streamlit.app](https://miolingo3.streamlit.app)

## Version Number Rules

```
0.9.0 → 0.9.1 → 0.9.2 → ... → 0.9.9 → 1.0.0 → 1.0.1 → 1.1.0 → 2.0.0
```

- **PATCH** (0.9.0 → 0.9.1): Bug fixes only, no new features
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible  
- **MAJOR** (0.9.9 → 1.0.0): Breaking changes OR first stable release

## Git Workflow

### Main Branch

- **main** - Always production-ready, deployed to Streamlit Cloud
- Never commit broken code to main
- Never merge without explicit permission

### Feature Development

```bash
# Start new feature
git checkout main
git pull myfork main
git checkout -b feature/feature-name

# Work on feature
# ... make changes ...
git add .
git commit -m "Descriptive commit message"

# Push feature branch
git push myfork feature/feature-name

# When ready to test/integrate
git checkout main
git merge feature/feature-name
# Test locally before pushing!

# If tests pass, update version and push
# (see "Releasing a New Version" below)
```

### Bug Fixes

```bash
# For bugs in production
git checkout main
git checkout -b bugfix/bug-description

# Fix bug
# ... make changes ...
git add .
git commit -m "Fix: description of bug fix"

# Merge and release patch version
git checkout main
git merge bugfix/bug-description
# Bump PATCH version (0.9.0 → 0.9.1)
```

### Hotfixes

```bash
# For critical production issues
git checkout main
git checkout -b hotfix/critical-issue

# Fix immediately
# ... make changes ...
git add .
git commit -m "Hotfix: critical issue description"

# Merge and release
git checkout main
git merge hotfix/critical-issue
# Bump PATCH version immediately
```

## Releasing a New Version

### Automated Method (Recommended)

Use the bump scripts for consistent version management:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Choose release type and run bump script
# For minor release (new features):
python scripts/bump_app.py minor tag push

# For major release (breaking changes):
python scripts/bump_app.py major tag push

# For patch (bug fixes) - typically not tagged:
python scripts/bump_app.py patch
git add -A
git commit -m "Fix: description"
git push origin main
```

The `bump_app.py` script automatically:
- Updates version in `src/app.py`
- Updates all documentation files
- Updates `APP_CHANGELOG.md` with new version entry
- Commits with standardized message (if `tag` specified)
- Creates git tag (if `tag` specified)
- Pushes to remote (if `push` specified)

See [BUMP_GUIDE.md](BUMP_GUIDE.md) for detailed bump script usage.

### Manual Method (Not Recommended)

<details>
<summary>Click to expand manual steps</summary>

### 1. Update Version Number

Edit `src/app.py`:

```python
__version__ = "3.1.0"  # Increment appropriately
```

### 2. Update Changelog

Edit `APP_CHANGELOG.md`:

```markdown
## [3.0.2] - 2025-11-XX

### Added
- New feature descriptions

### Fixed
- Bug fix descriptions

### Changed
- Changes to existing features
```

### 3. Update Documentation

Update version numbers in:
- `docs/app-docs/USER_GUIDE.md`
- `docs/app-docs/DEVELOPER_GUIDE.md`
- `docs/app-docs/TESTING_GUIDE.md`
- `README.md`
- `VERSION_WORKFLOW.md` (this file)
- `VERSION_CHECKLIST.md`

### 4. Commit Version Bump

```bash
git add -A
git commit -m "Bump version to 3.0.2

- Summary of main changes
- Key bug fixes
- Important notes"
```

### 5. Create Git Tag

```bash
# Tag must match version in src/app.py
git tag -a v3.0.2 -m "Version 3.0.2

- Feature/fix summary
- Important changes
- Known issues (if any)"
```

### 6. Push Everything

```bash
# Push main branch AND tags together
git push origin main --follow-tags
```

</details>

### 7. Verify Deployment

- Check Streamlit Cloud picks up changes at [miolingo3.streamlit.app](https://miolingo3.streamlit.app)
- Reboot app if needed via Streamlit dashboard
- Verify version number shows in sidebar

## Version Display

The app automatically shows version info in the sidebar:

```
Pronunciation Trainer
Version 3.0.1
```

This is pulled from `__version__` in `src/app.py`.

## Rollback Procedure

If a release has critical issues:

```bash
# Identify last working version
git tag -l  # List all tags

# Rollback to previous version
git checkout v0.9.0  # or previous working version

# Create hotfix branch from that point
git checkout -b hotfix/rollback-v0.9.1

# Or hard reset main (DANGEROUS - use with caution)
git reset --hard v0.9.0
git push myfork main --force  # Only if necessary!
```

## Best Practices

1. **Never push directly to main** - Always use branches
2. **Test locally first** - Run app before pushing
3. **Keep versions in sync** - Tag = version in app.py
4. **Document changes** - Update APP_CHANGELOG.md
5. **Meaningful commits** - Clear, descriptive messages
6. **Small increments** - Patch versions for fixes, minor for features
7. **Wait for permission** - Don't merge to main without approval

## Version History

- **3.0.x** - Current: Major restructuring, 6 languages, language materials browser
- **2.x.x** - Feature expansion, admin dashboard
- **1.0.0** - First stable release
- **0.9.x** - Beta/pre-release

### Major Version Milestones

- **3.0.0** - Repository reorganization, expanded to 6 languages (pt, fr, nl, de, es, it), language materials browser
- **2.0.0** - Admin dashboard, cost tracking, multi-user support
- **1.0.0** - First production-ready release with core features

## Viewing Version History

```bash
# List all versions
git tag -l

# Show specific version details
git show v0.9.0

# View changelog
cat APP_CHANGELOG.md

# Check current version
git describe --tags
```

## Remote Repository

- **origin**: `fairflow/miolingo` on GitHub (main repository)
- **Live deployment**: [miolingo3.streamlit.app](https://miolingo3.streamlit.app)

Push all changes to `origin main` branch.
