#!/usr/bin/env bash
# setup-worktree.sh — Bootstrap a fresh Claude Code worktree with the standard
# permissions allowlist (settings.local.json) and secrets.toml.
#
# Usage:
#   scripts/setup-worktree.sh                    # target = cwd
#   scripts/setup-worktree.sh <worktree-path>    # target = explicit path
#
# The template lives in scripts/worktree-settings.json (checked in).
# secrets.toml is copied from the main repo root (gitignored, never committed).
# Run once after EnterWorktree, or whenever either file is missing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/worktree-settings.json"
TARGET="${1:-$(pwd)}"
DEST="$TARGET/.claude"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: template not found at $TEMPLATE" >&2
    exit 1
fi

mkdir -p "$DEST"

if [[ -f "$DEST/settings.local.json" ]]; then
    echo "settings.local.json already exists at $DEST — skipping (delete it first to reset)."
else
    cp "$TEMPLATE" "$DEST/settings.local.json"
    echo "Installed $DEST/settings.local.json"
fi

# ── Copy secrets.toml from main repo (gitignored, never committed) ────────────
MAIN_ROOT="$(dirname "$(git -C "$TARGET" rev-parse --git-common-dir)")"
SECRETS_SRC="$MAIN_ROOT/.streamlit/secrets.toml"
SECRETS_DEST="$TARGET/.streamlit/secrets.toml"

if [[ -f "$SECRETS_SRC" ]]; then
    if [[ -f "$SECRETS_DEST" ]]; then
        echo "secrets.toml already exists at $SECRETS_DEST — skipping."
    else
        mkdir -p "$TARGET/.streamlit"
        cp "$SECRETS_SRC" "$SECRETS_DEST"
        echo "Installed $SECRETS_DEST"
    fi
else
    echo "WARNING: no secrets.toml found at $SECRETS_SRC — skipping."
fi
