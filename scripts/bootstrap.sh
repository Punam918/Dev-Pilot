#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3 >/dev/null || { echo "Python 3.11+ is required."; exit 1; }
command -v git >/dev/null || { echo "Git is required."; exit 1; }
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m devpilot init --demo
printf '\nStart with: source .venv/bin/activate && python -m devpilot serve\n'
printf 'Print the local token with: python -m devpilot token\n'
