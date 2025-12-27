#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
ROOT_DIR=${SCRIPT_DIR:h}

cd "$ROOT_DIR"

PORT=${1:-8501}
PID_FILE=".streamlit_${PORT}.pid"
LOG_FILE=".streamlit_${PORT}.log"

stop_existing() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "Stopping existing Streamlit (pid=$pid, port=$PORT)"
      kill "$pid" 2>/dev/null || true

      local i
      for i in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null; then
          break
        fi
        sleep 0.2
      done

      if kill -0 "$pid" 2>/dev/null; then
        echo "Process still alive; sending SIGKILL (pid=$pid)"
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  fi

  rm -f "$PID_FILE" 2>/dev/null || true
}

start_new() {
  if [[ ! -f "venv/bin/activate" ]]; then
    echo "ERROR: venv not found at venv/bin/activate (cwd=$PWD)" >&2
    return 1
  fi

  source venv/bin/activate

  if ! command -v streamlit >/dev/null 2>&1; then
    echo "ERROR: 'streamlit' not found after activating venv" >&2
    return 1
  fi

  echo "Starting Streamlit on port $PORT"
  streamlit run src/app.py --server.port "$PORT" --server.headless true > "$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  disown "$pid" 2>/dev/null || true

  echo "Started: pid=$pid"
  echo "Log: $LOG_FILE"
}

stop_existing
start_new
