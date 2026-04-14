#!/usr/bin/env bash
# setup-worktree.sh — Bootstrap a fresh Claude Code worktree with the standard
# permissions allowlist (settings.local.json).
#
# Usage:
#   scripts/setup-worktree.sh                    # target = cwd
#   scripts/setup-worktree.sh <worktree-path>    # target = explicit path
#
# The template lives in scripts/worktree-settings.json (checked in).
# Run once after EnterWorktree, or whenever settings.local.json is missing.

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
