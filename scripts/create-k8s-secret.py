#!/usr/bin/env python3
"""Create/update an existing-secret input without putting credentials in argv or Git."""
import argparse
import base64
import json
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--namespace", default="devpilot")
    p.add_argument("--context", required=True, help="Explicit kubectl context to prevent accidental deployment")
    args = p.parse_args()
    data = {}
    for name in ("api-token", "metrics-token"):
        value = (Path(".secrets") / name).read_bytes().strip()
        if len(value) < 24:
            raise SystemExit("Run python scripts/bootstrap.py first")
        data[name] = base64.b64encode(value).decode()
    key = Path(".secrets/llm-api-key")
    if key.exists():
        data["llm-api-key"] = base64.b64encode(key.read_bytes().strip()).decode()
    body = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "devpilot-secrets", "namespace": args.namespace}, "type": "Opaque", "data": data}
    subprocess.run(["kubectl", "--context", args.context, "apply", "-f", "-"], input=json.dumps(body), text=True, check=True)


if __name__ == "__main__":
    main()
