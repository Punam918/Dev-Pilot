#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Initializing local Dev-Pilot config and secrets"
python3 scripts/bootstrap.py

if [ ! -d ".venv" ]; then
  echo "==> Creating Python virtual environment"
  python3 -m venv .venv
fi

echo "==> Installing Python dependencies"
.venv/bin/python -m pip install -r requirements/dev.txt
.venv/bin/python -m pip install --no-deps -e .

echo
echo "Setup complete."
echo "Start the app with: ./run.sh"
