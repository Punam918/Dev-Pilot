"""Single-process file lease for serving and offline maintenance (Linux/WSL2).

This is defense in depth, not a distributed leader election mechanism.
"""
from __future__ import annotations
import fcntl
import os
from pathlib import Path


class InstanceLease:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "service.lock"
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise RuntimeError("DevPilot is already serving or being maintained; stop it first") from None
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
