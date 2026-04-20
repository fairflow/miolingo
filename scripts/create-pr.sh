#!/usr/bin/env bash
# create-pr.sh — safely create a GitHub PR for Miolingo
#
# Usage:
#   scripts/create-pr.sh --title "fix: thing (vX.Y.Z)" [--body "body text"]
#                        [--skip-version-check]
#
# Reads CLAUDE_BRANCH_TARGET from scripts/pr-config.env (update that file
# when the PR target branch changes, e.g. after a merge cycle).
#
# Safety checks performed:
#   1. No open PR already exists on the current branch
#   2. Version in src/config.py has been bumped since the last git tag
#   3. Branch is pushed to remote before PR is created

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/pr-config.env"

# ── Load config ──────────────────────────────────────────────────────────────
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: $CONFIG_FILE not found. Create it with CLAUDE_BRANCH_TARGET=<branch>." >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$CONFIG_FILE"

if [[ -z "${CLAUDE_BRANCH_TARGET:-}" ]]; then
  echo "ERROR: CLAUDE_BRANCH_TARGET not set in $CONFIG_FILE" >&2
  exit 1
fi

# ── Parse arguments ───────────────────────────────────────────────────────────
TITLE=""
BODY=""
SKIP_VERSION_CHECK=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)               TITLE="$2"; shift 2 ;;
    --body)                BODY="$2";  shift 2 ;;
    --skip-version-check)  SKIP_VERSION_CHECK=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$TITLE" ]]; then
  echo "Usage: scripts/create-pr.sh --title \"fix: thing (vX.Y.Z)\" [--body \"...\"]" >&2
  exit 1
fi

# ── Gather git context ────────────────────────────────────────────────────────
BASE_BRANCH="$CLAUDE_BRANCH_TARGET"
CURRENT_BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)"

echo "Branch : $CURRENT_BRANCH → $BASE_BRANCH"
echo "Title  : $TITLE"
echo ""

# ── Check 1: no open PR already exists ───────────────────────────────────────
echo "Checking for existing open PRs..."
OPEN_PR_COUNT="$(gh pr list --head "$CURRENT_BRANCH" --state open --json number 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")"
if [[ "$OPEN_PR_COUNT" -gt 0 ]]; then
  echo "ERROR: $OPEN_PR_COUNT open PR(s) already exist on '$CURRENT_BRANCH':" >&2
  gh pr list --head "$CURRENT_BRANCH" --state open >&2
  echo "" >&2
  echo "Merge or close the existing PR before raising a new one." >&2
  exit 1
fi
echo "  ✓ No open PRs on this branch"

# ── Check 2: version differs from base branch ────────────────────────────────
# We compare HEAD's __version__ against origin/$BASE_BRANCH rather than
# "last tag", because `bump_version.py --tag` places the newest tag AT HEAD
# (making `git describe`-based checks give an empty diff range).
if [[ "$SKIP_VERSION_CHECK" == false ]]; then
  VERSION_FILE="$PROJECT_ROOT/src/config.py"
  if [[ -f "$VERSION_FILE" ]]; then
    echo "Checking version bump..."
    # Fetch the base branch quietly so we compare against the latest state.
    git -C "$PROJECT_ROOT" fetch origin "$BASE_BRANCH" --quiet 2>/dev/null || true

    VERSION_AT_BASE="$(git -C "$PROJECT_ROOT" show "origin/$BASE_BRANCH:src/config.py" 2>/dev/null \
                       | grep -E '^__version__' || true)"
    VERSION_AT_HEAD="$(grep -E '^__version__' "$VERSION_FILE" || true)"

    if [[ -z "$VERSION_AT_BASE" ]]; then
      echo "  (could not read src/config.py on origin/$BASE_BRANCH — skipping version check)"
    elif [[ "$VERSION_AT_BASE" == "$VERSION_AT_HEAD" ]]; then
      echo "" >&2
      echo "WARNING: src/config.py __version__ is identical on this branch and origin/$BASE_BRANCH." >&2
      echo "  Expected a version bump for this PR." >&2
      echo "" >&2
      echo "  Run: source venv/bin/activate && python scripts/bump_version.py patch --suffix claude-dev --tag" >&2
      echo "  Then re-run this script. (Do NOT pass --push to bump_version.py — create-pr.sh handles the push.)" >&2
      echo "  Or re-run with --skip-version-check for tooling/docs-only PRs." >&2
      echo "" >&2
      exit 1
    else
      echo "  ✓ $VERSION_AT_HEAD  (base: $VERSION_AT_BASE)"
    fi
  fi
fi

# ── Push branch ───────────────────────────────────────────────────────────────
# Use the explicit `HEAD:refs/heads/<branch>` form so this push is safe even
# when the local branch has inherited a different upstream (e.g. dev-swept).
# The project's PreToolUse hook requires this form for the same reason.
echo "Pushing '$CURRENT_BRANCH'..."
git -C "$PROJECT_ROOT" push origin "HEAD:refs/heads/$CURRENT_BRANCH"
# Set the local upstream to the just-created remote branch so subsequent
# pushes (e.g. tags, follow-up commits) don't re-trigger the hook.
git -C "$PROJECT_ROOT" branch --set-upstream-to="origin/$CURRENT_BRANCH" "$CURRENT_BRANCH" >/dev/null 2>&1 || true
echo "  ✓ Pushed"

# ── Build auto-body if not provided ──────────────────────────────────────────
if [[ -z "$BODY" ]]; then
  COMMITS="$(git -C "$PROJECT_ROOT" log "origin/$BASE_BRANCH"..HEAD --oneline 2>/dev/null || git -C "$PROJECT_ROOT" log HEAD~5..HEAD --oneline)"
  BULLET_LIST="$(echo "$COMMITS" | sed 's/^/- /')"
  BODY="## Summary

$BULLET_LIST

## Test plan
- [ ] App starts without import errors
- [ ] Changed functionality verified in browser

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
fi

# ── Create PR ─────────────────────────────────────────────────────────────────
echo "Creating PR..."
PR_URL="$(gh pr create \
  --base "$BASE_BRANCH" \
  --head "$CURRENT_BRANCH" \
  --title "$TITLE" \
  --body "$BODY")"

echo ""
echo "✓ PR created: $PR_URL"
