#!/usr/bin/env python3
"""Pause new runs and wait for the active run. Does not approve or cancel actions."""
import argparse
import time
from pathlib import Path
import httpx


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8088")
    p.add_argument("--token-file", type=Path, default=Path(".secrets/api-token"))
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    token = args.token_file.read_text().strip()
    with httpx.Client(base_url=args.url, headers={"Authorization": "Bearer " + token}, timeout=10, trust_env=False) as client:
        response = client.post("/api/admin/resume" if args.resume else "/api/admin/drain")
        response.raise_for_status()
        if args.resume:
            print("New runs are accepted again.")
            return
        until = time.monotonic() + args.timeout
        while time.monotonic() < until:
            response = client.get("/api/config")
            response.raise_for_status()
            if not response.json()["active_run"]:
                print("Drained. No active run remains. Ready for a maintenance deployment.")
                return
            time.sleep(2)
        raise SystemExit("Drain timed out. Resolve pending approvals or cancel in UI; no deployment was performed.")


if __name__ == "__main__":
    main()
