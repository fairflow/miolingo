#!/usr/bin/env bash
# dev_server.sh — start Miolingo on a Claude-owned port
#
# Port convention:
#   8501–8599  Matthew (hands off)
#   8601–8699  Claude test/PR verification servers  (default 8601)
#   8701–8799  Claude Code Preview button / IDE launches  (launch.json uses 8701)
#   8702+      Admin app and other named launchers
#
# Usage:
#   scripts/dev_server.sh           # start on default port 8601
#   scripts/dev_server.sh 8602      # start on specific port
#   scripts/dev_server.sh stop      # stop default port (8601)
#   scripts/dev_server.sh stop 8602 # stop specific port

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$REPO_ROOT/src/app.py"
DEFAULT_PORT=8601

# venv lives in the main repo root, not in worktrees — find it via git
MAIN_REPO="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | xargs dirname || echo "$REPO_ROOT")"
VENV=""
for candidate in "$REPO_ROOT/venv" "$REPO_ROOT/.venv" "$MAIN_REPO/venv" "$MAIN_REPO/.venv"; do
    if [[ -f "$candidate/bin/activate" ]]; then
        VENV="$candidate"
        break
    fi
done

# ── forceful port-kill helper ────────────────────────────────────────────────
kill_port() {
    local port="$1"
    local pids
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
        return 0
    fi
    echo "Freeing port $port (PIDs: $pids)…"
    # SIGTERM first
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    # give it up to 3 seconds to exit gracefully
    local i
    for i in 1 2 3; do
        sleep 1
        pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
        [[ -z "$pids" ]] && return 0
    done
    # still alive — SIGKILL the survivors
    echo "Still alive — sending SIGKILL…"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
        echo "ERROR: could not free port $port (PIDs still present: $pids)" >&2
        return 1
    fi
    echo "Port $port freed."
}

# ── argument parsing ────────────────────────────────────────────────────────
ARG="${1:-}"
if [[ "$ARG" == "stop" ]]; then
    PORT="${2:-$DEFAULT_PORT}"
    pids="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
        kill_port "$PORT"
        echo "Done."
    else
        echo "Nothing running on port $PORT."
    fi
    exit 0
fi

PORT="${ARG:-$DEFAULT_PORT}"

# ── validate port range ─────────────────────────────────────────────────────
if (( PORT < 8601 )); then
    echo "ERROR: Claude servers must use ports 8601+ (got $PORT)." >&2
    echo "       Matthew owns 8501–8599." >&2
    exit 1
fi

# ── free the port if occupied ────────────────────────────────────────────────
kill_port "$PORT"

# ── activate venv ────────────────────────────────────────────────────────────
if [[ -z "$VENV" || ! -f "$VENV/bin/activate" ]]; then
    echo "ERROR: venv not found (tried $REPO_ROOT and $MAIN_REPO)" >&2
    exit 1
fi
source "$VENV/bin/activate"

# ── launch ───────────────────────────────────────────────────────────────────
echo "Starting Miolingo on http://localhost:$PORT  (Ctrl-C to stop)"
exec streamlit run "$APP" \
    --server.headless true \
    --server.port "$PORT"
