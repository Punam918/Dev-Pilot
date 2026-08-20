"""Bounded subprocess execution; argument vectors only, never shell=True."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from .safety import redact


def clean_env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", os.defpath), "HOME": "/tmp",
            "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONHASHSEED": "0",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0"}


def run_process(argv: list[str], cwd: Path, *, timeout: int = 60,
                max_output: int = 48_000, env: dict[str, str] | None = None, sanitize: bool = True) -> dict:
    started = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, env=env or clean_env(), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True)
    output = bytearray()
    timed_out = False
    output_limited = False
    selector = selectors.DefaultSelector()
    assert proc.stdout is not None
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() - started > timeout:
                timed_out = True
                break
            for key, _ in selector.select(timeout=0.05):
                block = os.read(key.fd, 4096)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                room = max_output - len(output)
                output.extend(block[:room])
                if len(block) > room:
                    output_limited = True
                    break
            if output_limited:
                break
        if timed_out or output_limited:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
    finally:
        selector.close()
        # Also clean descendants that kept running after the parent exited.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
        proc.stdout.close()
    return {"exit_code": proc.returncode, "output": (redact(output.decode("utf-8", "replace")) if sanitize else output.decode("utf-8", "replace")),
            "timed_out": timed_out, "output_limited": output_limited,
            "duration_ms": round((time.monotonic() - started) * 1000)}
