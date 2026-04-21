#!/usr/bin/env python3
"""
bump_version.py — Miolingo version management

Manages version numbers for the main app and admin dashboard.
Reads/writes the canonical version from src/config.py (app) or
src/miolingo-admin.py (admin), updates the changelog, and creates
git tags.

Version format
--------------
  Numeric part:  MAJOR.MINOR.PATCH  (Semantic Versioning 2.0)
  Full version:  MAJOR.MINOR.PATCH[-SUFFIX]
  Git tag:       v{full_version}           (app)
                 admin-v{full_version}     (admin)

Tag suffix convention
---------------------
  No suffix   — production/release build        e.g. v7.2.0
  Suffix      — development or phase milestone  e.g. v7.1.6-claude-dev-phase3

  Suffix format: {author}-{context}-{label}
    author   : who/what made the change  (claude, matthew, …)
    context  : type of work              (dev, exp, fix, …)
    label    : specific milestone        (phase2, audio, auth, …)
  All components are optional; at minimum use a single descriptive word.

Usage
-----
  python scripts/bump_version.py [TARGET] COMMAND [OPTIONS]

  TARGET (default: app)
    app     — main Streamlit app (src/config.py)
    admin   — admin dashboard   (src/miolingo-admin.py)

  COMMAND
    show                  Print current version and exit
    major                 Bump major version  (1.2.3 → 2.0.0)
    minor                 Bump minor version  (1.2.3 → 1.3.0)
    patch                 Bump patch version  (1.2.3 → 1.2.4)
    set X.Y.Z             Set explicit numeric version

  OPTIONS
    --suffix LABEL        Append -LABEL to the version  (e.g. claude-dev-phase3)
    --tag                 Create annotated git tag after commit
    --push                Push commits and tags to remote (implies commit)
    --notes "TEXT"        One-line summary written to the changelog.
                          REQUIRED unless --no-notes is given. May be passed
                          multiple times (each becomes a bullet).  Also accepts
                          a single string with '\\n' — each line becomes a
                          bullet. Bullets copy verbatim; don't prefix with '-'.
    --kind KIND           Changelog section for the bullets.
                          One of: added | changed | fixed | removed | deprecated
                          | security. Default: changed.
    --no-notes            Skip the --notes requirement. Reserved for emergency
                          bumps / tooling-only re-tags — DO NOT use for
                          feature/fix/refactor PRs.

Examples
--------
  python scripts/bump_version.py show
  python scripts/bump_version.py patch
  python scripts/bump_version.py minor --tag
  python scripts/bump_version.py set 7.1.6 --suffix claude-dev-phase2 --tag
  python scripts/bump_version.py minor --tag --push
  python scripts/bump_version.py admin minor --tag

Note: activate the project virtual environment first.
"""

import re
import sys
import subprocess
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

TARGETS = {
    "app": {
        "version_file": PROJECT_ROOT / "src" / "config.py",
        "changelog_file": PROJECT_ROOT / "APP_CHANGELOG.md",
        "version_pattern": r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
        "tag_prefix": "v",
    },
    "admin": {
        "version_file": PROJECT_ROOT / "src" / "unified_admin.py",
        "changelog_file": PROJECT_ROOT / "ADMIN_CHANGELOG.md",
        "version_pattern": r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
        "tag_prefix": "admin-v",
    },
}

# ---------------------------------------------------------------------------
# Version parsing helpers
# ---------------------------------------------------------------------------

SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)(.*)$')


def parse_version(v: str):
    """Return (major, minor, patch, suffix_str) from a version string."""
    m = SEMVER_RE.match(v.strip())
    if not m:
        raise ValueError(f"Cannot parse version: {v!r}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    suffix = m.group(4)  # e.g. "-claude-dev-phase2" or ""
    return major, minor, patch, suffix


def make_version(major: int, minor: int, patch: int, suffix: str = "") -> str:
    """Compose a version string, e.g. '7.1.6' or '7.1.6-claude-dev-phase2'."""
    base = f"{major}.{minor}.{patch}"
    if suffix:
        suffix = suffix if suffix.startswith("-") else f"-{suffix}"
        return f"{base}{suffix}"
    return base


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def read_version(target_cfg: dict) -> str:
    """Read the current __version__ value from the target source file."""
    path = target_cfg["version_file"]
    if not path.exists():
        raise FileNotFoundError(f"Version file not found: {path}")
    content = path.read_text()
    m = re.search(target_cfg["version_pattern"], content)
    if not m:
        raise ValueError(f"No __version__ found in {path}")
    return m.group(2)


def write_version(target_cfg: dict, new_version: str) -> None:
    """Write the new __version__ value into the target source file."""
    path = target_cfg["version_file"]
    content = path.read_text()
    new_content = re.sub(
        target_cfg["version_pattern"],
        lambda mo: f"{mo.group(1)}{new_version}{mo.group(3)}",
        content,
        count=1,
    )
    if new_content == content:
        raise RuntimeError(f"No replacement made in {path} — pattern mismatch?")
    path.write_text(new_content)


_KIND_HEADINGS = {
    "added": "Added",
    "changed": "Changed",
    "fixed": "Fixed",
    "removed": "Removed",
    "deprecated": "Deprecated",
    "security": "Security",
}


def update_changelog(
    target_cfg: dict,
    new_version: str,
    notes: list[str] | None = None,
    kind: str = "changed",
) -> bool:
    """Prepend a new section to the changelog. Returns True if file was updated."""
    path = target_cfg["changelog_file"]
    if not path.exists():
        print(f"  ⚠️  Changelog not found, skipping: {path}")
        return False

    today = date.today().isoformat()
    heading = _KIND_HEADINGS.get(kind.lower(), "Changed")
    if notes:
        bullets = "\n".join(f"- {line}" for line in notes)
    else:
        bullets = "- Version bump"
    entry = f"## [{new_version}] - {today}\n\n### {heading}\n\n{bullets}\n\n\n"

    content = path.read_text()
    # Insert before the first existing ## [ entry
    lines = content.splitlines(keepends=True)
    insert_at = next(
        (i for i, ln in enumerate(lines) if ln.startswith("## [")), len(lines)
    )
    lines.insert(insert_at, entry)
    path.write_text("".join(lines))
    return True


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

def git_commit(files: list[Path], message: str) -> None:
    subprocess.run(["git", "add"] + [str(f) for f in files], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)


def git_tag(tag_name: str, message: str) -> None:
    subprocess.run(["git", "tag", "-a", tag_name, "-m", message], check=True)


def git_push() -> None:
    subprocess.run(["git", "push", "origin", "HEAD"], check=True)
    subprocess.run(["git", "push", "origin", "--tags"], check=True)


# ---------------------------------------------------------------------------
# Argument parsing (no argparse dependency)
# ---------------------------------------------------------------------------

def parse_args(argv):
    """
    Returns (target, command, set_version, suffix, do_tag, do_push,
             notes, kind, no_notes).
    """
    args = list(argv[1:])

    # Extract boolean flags
    do_tag = "--tag" in args
    do_push = "--push" in args
    no_notes = "--no-notes" in args
    for flag in ("--tag", "--push", "--no-notes"):
        while flag in args:
            args.remove(flag)

    def _take_value(flag: str) -> str | None:
        nonlocal args
        if flag not in args:
            return None
        idx = args.index(flag)
        if idx + 1 >= len(args):
            print(f"Error: {flag} requires a value", file=sys.stderr)
            sys.exit(1)
        val = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
        return val

    suffix = _take_value("--suffix") or ""
    kind = (_take_value("--kind") or "changed").lower()
    if kind not in _KIND_HEADINGS:
        print(
            f"Error: --kind must be one of {sorted(_KIND_HEADINGS)}, got {kind!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Collect all --notes values (repeatable).
    notes: list[str] = []
    while "--notes" in args:
        val = _take_value("--notes")
        if val:
            # A single --notes may carry '\n' or real newlines; split either.
            for line in val.replace("\\n", "\n").splitlines():
                line = line.strip().lstrip("-").strip()
                if line:
                    notes.append(line)

    if not args:
        print(__doc__)
        sys.exit(0)

    # Optional target as first positional arg
    target = "app"
    if args[0] in TARGETS:
        target = args.pop(0)

    if not args:
        print(__doc__)
        sys.exit(0)

    command = args[0].lower()
    set_version = None

    if command == "set":
        if len(args) < 2:
            print("Error: 'set' requires a version number, e.g. set 7.1.6", file=sys.stderr)
            sys.exit(1)
        set_version = args[1]
        # Validate
        try:
            parse_version(set_version)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    return (target, command, set_version, suffix, do_tag, do_push,
            notes, kind, no_notes)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    (target_name, command, set_version, suffix, do_tag, do_push,
     notes, kind, no_notes) = parse_args(sys.argv)

    # Enforce --notes for any real bump (not `show`). --no-notes opts out.
    if command != "show" and not notes and not no_notes:
        print(
            "Error: --notes \"summary\" is required.\n"
            "  A changelog entry that just says 'Version bump' is useless —\n"
            "  summarise what changed so future readers (and you) know why.\n\n"
            "  Examples:\n"
            "    --notes \"Post-capture edit form for vocab entries.\"\n"
            "    --notes \"Fix: auto-fill no longer overwrites translations.\" --kind fixed\n"
            "    --notes \"line one\" --notes \"line two\"         # two bullets\n"
            "    --notes \"line one\\nline two\"                   # same, one arg\n\n"
            "  For emergency bumps / tooling-only re-tags only, pass --no-notes.",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = TARGETS[target_name]

    current_full = read_version(cfg)
    current_major, current_minor, current_patch, current_suffix = parse_version(current_full)

    if command == "show":
        tag = f"{cfg['tag_prefix']}{current_full}"
        print(f"Target  : {target_name}")
        print(f"Version : {current_full}")
        print(f"Git tag : {tag}")
        return

    # Determine new numeric version
    if command == "major":
        new_major, new_minor, new_patch = current_major + 1, 0, 0
    elif command == "minor":
        new_major, new_minor, new_patch = current_major, current_minor + 1, 0
    elif command == "patch":
        new_major, new_minor, new_patch = current_major, current_minor, current_patch + 1
    elif command == "set":
        new_major, new_minor, new_patch, _ = parse_version(set_version)
    else:
        print(f"Error: unknown command '{command}'", file=sys.stderr)
        print("Use: show | major | minor | patch | set X.Y.Z", file=sys.stderr)
        sys.exit(1)

    new_full = make_version(new_major, new_minor, new_patch, suffix)
    tag_name = f"{cfg['tag_prefix']}{new_full}"

    print(f"📦  {target_name}: {current_full} → {new_full}")
    if suffix:
        print(f"    suffix: -{suffix}")

    # Update source file
    write_version(cfg, new_full)
    print(f"  ✅  {cfg['version_file'].relative_to(PROJECT_ROOT)}")

    # Update changelog
    changelog_updated = update_changelog(cfg, new_full, notes=notes, kind=kind)
    if changelog_updated:
        print(f"  ✅  {cfg['changelog_file'].relative_to(PROJECT_ROOT)}")

    changed_files = [cfg["version_file"]]
    if changelog_updated:
        changed_files.append(cfg["changelog_file"])

    if do_tag or do_push:
        commit_msg = f"{tag_name}: version bump"
        git_commit(changed_files, commit_msg)
        print(f"\n  📝  Committed: {commit_msg}")

    if do_tag:
        git_tag(tag_name, f"Version {new_full}")
        print(f"  🏷️   Tagged:    {tag_name}")

    if do_push:
        git_push()
        print("  🚀  Pushed to remote")

    if not (do_tag or do_push):
        print(f"\n💡 To commit and tag, re-run with --tag:")
        print(f"   python scripts/bump_version.py {target_name} set {new_major}.{new_minor}.{new_patch}" +
              (f" --suffix {suffix}" if suffix else "") + " --tag")


if __name__ == "__main__":
    main()
