#!/usr/bin/env python3
"""Exercise the real UI against an isolated, trusted scripted fixture and save screenshots.

Requires the optional .[ui] dependency and Chromium. Never points at another repository.
This is an integration replay, not an LLM demonstration.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from devpilot.demo import seed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs")
    parser.add_argument("--chromium", default=shutil.which("chromium"))
    args = parser.parse_args()
    from playwright.sync_api import expect, sync_playwright
    import httpx

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="devpilot-ui-") as directory:
        base = Path(directory)
        seed(base / "workspace")
        token = secrets.token_urlsafe(32)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = dict(os.environ)
        env.update(DP_PROVIDER="demo", DP_RUNNER="host-trusted", DP_TRUST_LOCAL_CODE="true",
                   DP_WORKSPACE_DIR=str(base / "workspace"), DP_DATA_DIR=str(base / "state"),
                   DP_HOST="127.0.0.1", DP_PORT=str(port), DP_API_TOKEN=token, DP_DOCKER_TOOLS="false")
        url = f"http://127.0.0.1:{port}"
        with (base / "server.log").open("w") as log:
            process = subprocess.Popen([sys.executable, "-m", "devpilot", "serve"], cwd=ROOT,
                         env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                with httpx.Client(timeout=2, trust_env=False) as client:
                    for _ in range(100):
                        try:
                            if client.get(url + "/healthz").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if process.poll() is not None:
                            raise RuntimeError("Demo API exited before becoming healthy")
                        time.sleep(.1)
                    else:
                        raise TimeoutError("Demo API did not start")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True, executable_path=args.chromium,
                                                         args=["--no-sandbox"])
                    context = browser.new_context(viewport={"width": 1500, "height": 1180}, device_scale_factor=1)
                    page = context.new_page()
                    errors: list[str] = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(url)
                    page.fill("#token", token)
                    page.click("#connect")
                    expect(page.locator("#run")).to_be_enabled(timeout=20_000)
                    page.click("#run")
                    approvals: list[str] = []
                    edit_captured = False
                    deadline = time.monotonic() + 100
                    while time.monotonic() < deadline:
                        status = page.locator("#run-status").inner_text()
                        if status == "COMPLETED":
                            break
                        if status in {"FAILED", "CANCELLED", "LIMIT REACHED"}:
                            raise RuntimeError("Unexpected terminal UI status: " + status)
                        if page.locator("#approval").is_visible() and page.locator("#approve").is_enabled():
                            tool = page.locator("#approval-title").inner_text()
                            approvals.append(tool)
                            if tool == "files__replace_text" and not edit_captured:
                                page.screenshot(path=str(args.out / "ui-approval.png"), full_page=True)
                                edit_captured = True
                            page.click("#approve")
                            page.wait_for_timeout(600)
                        page.wait_for_timeout(150)
                    else:
                        raise TimeoutError("UI run did not complete")
                    page.locator("#verification.good").wait_for(state="visible", timeout=20_000)
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(args.out / "ui-overview.png"), full_page=True)
                    with page.expect_download() as download:
                        page.locator('[data-download="patch"]').click()
                    patch = Path(download.value.path()).read_text()
                    assert 'localhost' in patch and 'redis' in patch
                    assert edit_captured and len(approvals) == 3
                    assert not errors, errors
                    result = {"status": "passed", "provider": "scripted demo; no LLM", "browser": browser.version,
                              "approvals": approvals, "verified_indicator": True,
                              "patch_download_checked": True, "page_errors": errors,
                              "screenshots": ["ui-approval.png", "ui-overview.png"]}
                    (ROOT / "outputs" / "ui-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
                    print(json.dumps(result, indent=2))
                    browser.close()
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()


if __name__ == "__main__":
    main()
