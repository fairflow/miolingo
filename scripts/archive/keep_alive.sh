#!/bin/zsh
# Keep Mac awake and run Streamlit + Cloudflare Tunnel
# Run with: zsh scripts/keep_alive.sh

echo "🚀 Starting Miolingo with keep-alive..."

# Prevent sleep while this script runs
caffeinate -disu -w $$ &
CAFFEINATE_PID=$!
echo "☕ Caffeinate active (PID: $CAFFEINATE_PID)"

# Cleanup function
cleanup() {
    echo "🛑 Stopping services..."
    kill $CAFFEINATE_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

# Keep script running
echo "✅ Mac will stay awake. Press Ctrl+C to stop."
wait
