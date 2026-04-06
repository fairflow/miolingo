#!/usr/bin/env bash
# dev_server.sh — start Miolingo on a Claude-owned port (8601+)
#
# Usage:
#   scripts/dev_server.sh           # start on default port 8601
#   scripts/dev_server.sh 8602      # start on specific port
#   scripts/dev_server.sh stop      # kill whatever is on PORT
#
# Convention: Matthew owns 8501–8599; Claude owns 8601+.
# This script always frees the target port before starting.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$REPO_ROOT/src/app.py"

# venv lives in the main repo root, not in worktrees — find it via git
MAIN_REPO="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | xargs dirname || echo "$REPO_ROOT")"
VENV=""
for candidate in "$REPO_ROOT/venv" "$REPO_ROOT/.venv" "$MAIN_REPO/venv" "$MAIN_REPO/.venv"; do
    if [[ -f "$candidate/bin/activate" ]]; then
        VENV="$candidate"
        break
    fi
done
DEFAULT_PORT=8601

# ── argument parsing ────────────────────────────────────────────────────────
ARG="${1:-}"
if [[ "$ARG" == "stop" ]]; then
    PORT="${2:-$DEFAULT_PORT}"
    PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
    if [[ -n "$PID" ]]; then
        echo "Stopping process $PID on port $PORT…"
        kill "$PID" && echo "Done." || echo "Could not kill $PID"
    else
        echo "Nothing running on port $PORT."
    fi
    exit 0
fi

PORT="${ARG:-$DEFAULT_PORT}"

# ── validate port range ─────────────────────────────────────────────────────
if (( PORT < 8601 || PORT > 8699 )); then
    echo "ERROR: Claude dev servers must use ports 8601–8699 (got $PORT)." >&2
    echo "       Matthew owns 8501–8599." >&2
    exit 1
fi

# ── free the port if occupied ────────────────────────────────────────────────
PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
if [[ -n "$PID" ]]; then
    echo "Port $PORT in use by PID $PID — freeing it…"
    kill "$PID"
    # brief wait for the socket to close
    sleep 1
fi

# ── activate venv ────────────────────────────────────────────────────────────
if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "ERROR: venv not found at $VENV" >&2
    exit 1
fi
source "$VENV/bin/activate"

# ── launch ───────────────────────────────────────────────────────────────────
echo "Starting Miolingo on http://localhost:$PORT  (Ctrl-C to stop)"
exec streamlit run "$APP" \
    --server.headless true \
    --server.port "$PORT"
