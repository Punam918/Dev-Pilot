#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PORT="${DP_PORT:-8091}"
DATA_DIR="${DP_DATA_DIR:-.devpilot-local}"
HOST="${DP_HOST:-127.0.0.1}"
PID_FILE="$DATA_DIR/server.pid"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run ./setup.sh first."
  exit 1
fi

mkdir -p "$DATA_DIR"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Dev-Pilot is already running with PID $old_pid."
    echo "Open: http://$HOST:$PORT"
    echo "Stop it with: ./stop.sh"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

echo "==> Starting Dev-Pilot"
echo "URL:   http://$HOST:$PORT"
echo "Token: $(DP_DATA_DIR="$DATA_DIR" .venv/bin/python -m devpilot token)"
echo
echo "Press Ctrl+C to stop, or run ./stop.sh from another terminal."

DP_HOST="$HOST" DP_PORT="$PORT" DP_DATA_DIR="$DATA_DIR" .venv/bin/python -m devpilot serve --seed &
pid="$!"
echo "$pid" > "$PID_FILE"

cleanup() {
  rm -f "$PID_FILE"
}
trap cleanup EXIT

wait "$pid"
