#!/usr/bin/env python3
"""Initialize private local configuration without overwriting existing secrets."""
from __future__ import annotations
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    secret_dir = ROOT / ".secrets"
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    secret_dir.chmod(0o700)
    for name in ("api-token", "metrics-token", "grafana-password"):
        path = secret_dir / name
        if not path.exists():
            path.write_text(secrets.token_urlsafe(32) + "\n")
        # Compose file secrets are bind-mounted: this lets its non-root users read
        # the mounted file. The 0700 PARENT keeps other host users out.
        path.chmod(0o644)
    env = ROOT / ".env"
    if not env.exists():
        env.write_text("\n".join([
            "# Local demo. Never commit this file or .secrets/.",
            "DP_PROVIDER=demo", "DP_MODEL=qwen3:4b", "DP_BASE_URL=http://127.0.0.1:11434/v1",
            "DP_API_TOKEN_FILE=.secrets/api-token", "DP_METRICS_TOKEN_FILE=.secrets/metrics-token",
            "DP_DATA_DIR=.devpilot", "DP_WORKSPACE_DIR=workspace", "DP_PORT=8088",
            "DP_RUNNER=host-trusted", "DP_TRUST_LOCAL_CODE=true", "DP_DOCKER_TOOLS=false", ""]))
        env.chmod(0o600)
        print("Created .env for the TRUSTED bundled demo on port 8088.")
    else:
        print("Existing .env preserved. Compose uses .secrets/; host Python uses your .env.")
    print("Secrets initialized without printing their values. Compose: docker compose up -d --build")
    print("Host Python: python -m devpilot serve --seed")


if __name__ == "__main__":
    main()
