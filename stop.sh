#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DATA_DIR="${DP_DATA_DIR:-.devpilot-local}"
PID_FILE="$DATA_DIR/server.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "No Dev-Pilot PID file found at $PID_FILE."
  echo "If a server is still running, stop it with Ctrl+C in its terminal."
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$pid" ]; then
  rm -f "$PID_FILE"
  echo "Removed empty PID file."
  exit 0
fi

if kill -0 "$pid" 2>/dev/null; then
  echo "Stopping Dev-Pilot PID $pid"
  kill "$pid"
else
  echo "PID $pid is not running."
fi

rm -f "$PID_FILE"
echo "Stopped."
