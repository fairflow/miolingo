#!/usr/bin/env bash
# Quick smoke test: verify the app starts cleanly on a test port.
# Usage: scripts/test_app_starts.sh [port]
#   port  — TCP port to use (default 8502)
#
# Exit 0 if the app serves HTTP within 15 s, exit 1 otherwise.
# Cleans up the Streamlit process on exit.

set -euo pipefail

PORT="${1:-8502}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- locate venv --------------------------------------------------------
for candidate in "$REPO_ROOT/venv" "$REPO_ROOT/.venv"; do
    if [[ -f "$candidate/bin/activate" ]]; then
        VENV="$candidate"
        break
    fi
done

# Walk up to main repo root if we're in a worktree
if [[ -z "${VENV:-}" ]]; then
    MAIN_ROOT="$(git -C "$REPO_ROOT" rev-parse --git-common-dir 2>/dev/null | sed 's|/\.git$||')"
    for candidate in "$MAIN_ROOT/venv" "$MAIN_ROOT/.venv"; do
        if [[ -f "$candidate/bin/activate" ]]; then
            VENV="$candidate"
            break
        fi
    done
fi

if [[ -z "${VENV:-}" ]]; then
    echo "FAIL: could not find venv/ or .venv/ in repo root or main repo" >&2
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# --- start Streamlit in background --------------------------------------
cd "$REPO_ROOT"
streamlit run src/app.py \
    --server.port "$PORT" \
    --server.headless true \
    > /dev/null 2>&1 &
APP_PID=$!

cleanup() {
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT

# --- poll until HTTP responds or timeout --------------------------------
MAX_WAIT=15
for i in $(seq 1 "$MAX_WAIT"); do
    if curl -s -o /dev/null -w '' "http://localhost:$PORT/_stcore/health" 2>/dev/null; then
        echo "OK: app responding on port $PORT (${i}s)"
        exit 0
    fi
    sleep 1
done

echo "FAIL: app did not respond on port $PORT within ${MAX_WAIT}s" >&2
exit 1
