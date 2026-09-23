#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "Install uv from its official distribution first." >&2; exit 1; }
# This overwrites dependency pins; review the diff, rerun CI, and scan the resulting images.
uv pip compile --generate-hashes requirements/runtime.in -o requirements/runtime.txt
