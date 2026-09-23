#!/usr/bin/env bash
# Offline backup of the named DevPilot Compose volume. No docker system prune.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "${1:-}" == "--allow-downtime" ]] || { echo 'Usage: bash scripts/compose-backup.sh --allow-downtime' >&2; exit 2; }
# Requires the Python dev environment for the authenticated drain helper.
python scripts/drain.py
mkdir -p backups
chmod 700 backups
OUT="backups/devpilot-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
[[ ! -e "$OUT" ]] || { echo 'Backup path exists' >&2; exit 2; }
umask 077
# On an interrupted backup, restart the original service without deleting data.
trap 'docker compose start devpilot >/dev/null || true' EXIT
docker compose stop devpilot
if docker compose run --rm --no-deps -T devpilot python -c 'from pathlib import Path;import shutil,sys;from devpilot.config import Settings;from devpilot.backup import create_backup;p=Path("/tmp/archive.tar.gz");create_backup(Settings(),p);f=p.open("rb");shutil.copyfileobj(f,sys.stdout.buffer)' > "$OUT"; then
  sha256sum "$OUT"
  printf 'Backup: %s (sensitive; not encrypted). Restore into a NEW directory first.\n' "$OUT"
else
  rm -f "$OUT"
  echo 'Backup failed. Partial archive removed; original volume retained.' >&2
  exit 1
fi
