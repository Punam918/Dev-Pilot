"""Filesystem boundaries, redaction, and single-use action capabilities.

These controls reduce accidental damage; they do not turn a process into a VM.
The operator and the DevPilot installation are trusted. Repository content is not.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import time
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILE_BYTES = 120_000
MAX_REPO_BYTES = 12_000_000
MAX_REPO_FILES = 1500
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".devpilot", "dist", "build"}
SECRET_NAMES = {"id_rsa", "id_ed25519", ".npmrc", ".pypirc", "credentials", "credentials.json", "secrets.json", "secrets.yaml"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".ini", ".cfg", ".sh", ".sql", ".log", ".csv", ".xml"}


class SafetyError(ValueError):
    """An operation violates an explicit workspace or permission boundary."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def sensitive_name(name: str) -> bool:
    low = name.lower()
    return ((low.startswith(".env") and low not in {".env.example", ".env.sample"})
            or low in SECRET_NAMES or Path(low).suffix in SECRET_SUFFIXES)


def redact(text: str) -> str:
    """Best effort only: not a guarantee that arbitrary source/logs contain no secrets."""
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)
    text = re.sub(r"\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_\-]{12,}\b", "[REDACTED]", text)
    text = re.sub(r"(?im)((?:api[_-]?key|password|secret|access[_-]?token)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", text)
    return text


class Workspace:
    def __init__(self, root: Path):
        if root.is_symlink():
            raise SafetyError("Workspace root cannot be a symlink")
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise SafetyError("Workspace must be a directory")

    def path(self, relative: str, *, existing: bool = True) -> Path:
        if not relative or "\\" in relative or "\x00" in relative:
            raise SafetyError("Use a nonempty POSIX relative path")
        parts = PurePosixPath(relative).parts
        if PurePosixPath(relative).is_absolute() or any(p in {"..", ".git"} for p in parts):
            raise SafetyError("Absolute paths, parent traversal, and .git access are forbidden")
        if any(sensitive_name(p) for p in parts):
            raise SafetyError("Secret-bearing paths are excluded")
        current = self.root
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise SafetyError("Symlinks are not permitted")
        resolved = current.resolve(strict=existing)
        if not resolved.is_relative_to(self.root):
            raise SafetyError("Path escapes the workspace")
        if existing and resolved.is_file():
            info = resolved.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SafetyError("Only ordinary, single-link files are allowed")
        return resolved

    def files(self) -> list[str]:
        found: list[str] = []
        for base, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not sensitive_name(d)
                             and not (Path(base) / d).is_symlink())
            for name in sorted(names):
                if sensitive_name(name):
                    continue
                rel = (Path(base) / name).relative_to(self.root).as_posix()
                try:
                    path = self.path(rel)
                    if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                        found.append(rel)
                except (SafetyError, OSError):
                    continue
                if len(found) > MAX_REPO_FILES:
                    raise SafetyError("Repository exceeds the file-count budget")
        return found

    def read_bytes(self, relative: str) -> bytes:
        path = self.path(relative)
        if not path.is_file():
            raise SafetyError("Expected a file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise SafetyError("File exceeds the size budget")
        # O_NOFOLLOW also protects the final component between check and open.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SafetyError("Only ordinary, single-link files are allowed")
            content = stream.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise SafetyError("File exceeds the size budget")
        return content

    def read(self, relative: str) -> str:
        raw = self.read_bytes(relative)
        if b"\0" in raw:
            raise SafetyError("Binary files are not text resources")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SafetyError("File is not UTF-8 text") from exc

    def fingerprint(self) -> str:
        items = [(name, digest(self.read_bytes(name))) for name in self.files()]
        return digest(canonical(items))

    def edit_preview(self, path: str, old: str, new: str, expected_sha256: str) -> tuple[str, str]:
        import difflib
        parts = PurePosixPath(path).parts
        if "tests" in parts or Path(path).name.startswith("test_") or Path(path).name == "conftest.py":
            raise SafetyError("Changing tests is disabled; repair application code, not the checks")
        if not old or old == new:
            raise SafetyError("Replacement must be nonempty and change the file")
        before = self.read(path)
        if digest(before) != expected_sha256:
            raise SafetyError("Stale file hash: read the current file before editing")
        if before.count(old) != 1:
            raise SafetyError("Old text must match exactly once")
        after = before.replace(old, new, 1)
        if len(after.encode()) > MAX_FILE_BYTES:
            raise SafetyError("Replacement exceeds the file-size budget")
        diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                           fromfile=f"a/{path}", tofile=f"b/{path}"))
        return after, diff

    def replace(self, path: str, old: str, new: str, expected_sha256: str) -> dict:
        after, diff = self.edit_preview(path, old, new, expected_sha256)
        target = self.path(path)
        temporary = target.with_name(f".dp-{secrets.token_hex(8)}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="") as stream:
                stream.write(after)
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path": path, "sha256": digest(after), "diff": diff}


def copy_workspace(source: Path, destination: Path) -> dict:
    """Copy regular bounded files, never Git hooks/config or local credentials."""
    original = Workspace(source)
    names = original.files()
    total = sum(original.path(n).stat().st_size for n in names)
    if total > MAX_REPO_BYTES:
        raise SafetyError("Repository exceeds the total-size budget")
    destination.mkdir(parents=True, exist_ok=False, mode=0o755)
    for name in names:
        data = original.read_bytes(name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        target.write_bytes(data)
        target.chmod(0o644)
    return {"files": len(names), "bytes": total, "excluded": "symlinks, large files, credentials, caches, .git"}


class Capabilities:
    """Bound to one server process, action, arguments, and exact workspace snapshot."""
    def __init__(self, secret: str):
        self.secret = secret.encode()
        self.used: set[str] = set()

    def issue(self, tool: str, arguments: dict, snapshot: str, ttl: int = 60) -> str:
        payload = {"tool": tool, "args": digest(canonical(arguments)), "snapshot": snapshot,
                   "expires": time.time() + ttl, "nonce": secrets.token_hex(16)}
        raw = canonical(payload).encode()
        body = base64.urlsafe_b64encode(raw).decode()
        mac = hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
        return f"{body}.{mac}"

    def verify(self, token: str, tool: str, arguments: dict, snapshot: str) -> None:
        try:
            body, mac = token.split(".", 1)
            expected = hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, mac):
                raise SafetyError("Invalid approval signature")
            payload = json.loads(base64.urlsafe_b64decode(body))
            valid = (payload["tool"] == tool and payload["args"] == digest(canonical(arguments))
                     and payload["snapshot"] == snapshot and payload["expires"] >= time.time()
                     and payload["nonce"] not in self.used)
            if not valid:
                raise SafetyError("Approval expired, was replayed, or no longer matches the action/snapshot")
            self.used.add(payload["nonce"])
        except SafetyError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            raise SafetyError("Malformed approval capability") from exc


def redact_tree(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_tree(item) for key, item in value.items()}
    return value
