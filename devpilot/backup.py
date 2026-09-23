"""Offline, integrity-checked state backups. Archives contain sensitive source/logs.

Never run this while the API is serving. Credentials are excluded; restore them
separately. This is an archive, not encryption or off-site storage.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import io
import json
import sqlite3
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from . import __version__
from .config import Settings
from .lease import InstanceLease
from .safety import sensitive_name

MAX_BYTES = 1_000_000_000
EXCLUDED = {"access-token", "service.lock", "audit.sqlite3-wal", "audit.sqlite3-shm"}


def create_backup(settings: Settings, output: Path) -> dict:
    output = output.resolve()
    if output.is_relative_to(settings.data_dir) or output.is_relative_to(settings.workspace_dir):
        raise ValueError("Write backups outside state and workspace directories")
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing backup")
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": 1, "version": __version__, "files": {}}
    with InstanceLease(settings.data_dir), tempfile.TemporaryDirectory() as temporary:
        database = settings.data_dir / "audit.sqlite3"
        copy = Path(temporary) / "audit.sqlite3"
        if database.exists():
            with closing(sqlite3.connect(database)) as src, closing(sqlite3.connect(copy)) as dst:
                src.backup(dst)
        total = 0
        try:
            with tarfile.open(output, "w:gz") as archive:
                for prefix, root in (("state", settings.data_dir), ("workspace", settings.workspace_dir)):
                    for path in sorted(root.rglob("*")):
                        relative = path.relative_to(root)
                        if any(sensitive_name(part) or part in {".secrets", "__pycache__", ".pytest_cache"} for part in relative.parts):
                            continue
                        if path.is_symlink() or any(x.is_symlink() for x in path.parents if x != root.parent):
                            raise ValueError("Symlinks are not accepted in backup input")
                        if not path.is_file() or path.name in EXCLUDED:
                            continue
                        source = copy if prefix == "state" and relative.as_posix() == "audit.sqlite3" else path
                        raw = source.read_bytes()
                        total += len(raw)
                        if total > MAX_BYTES:
                            raise ValueError("Backup exceeds 1GB; archive runs before retrying")
                        name = prefix + "/" + relative.as_posix()
                        entry = tarfile.TarInfo(name)
                        entry.size, entry.mode = len(raw), 0o600
                        archive.addfile(entry, io.BytesIO(raw))
                        manifest["files"][name] = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                raw = (json.dumps(manifest, indent=2) + "\n").encode()
                entry = tarfile.TarInfo("manifest.json")
                entry.size, entry.mode = len(raw), 0o600
                archive.addfile(entry, io.BytesIO(raw))
            output.chmod(0o600)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return manifest


def restore_backup(archive_path: Path, destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError("Restore into a new directory; never overwrite live state")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 200_000 or sum(m.size for m in members) > MAX_BYTES + 20_000_000:
            raise ValueError("Backup exceeds the restore budget")
        names = [m.name for m in members]
        if len(set(names)) != len(names) or names.count("manifest.json") != 1:
            raise ValueError("Duplicate members or missing manifest")
        for member in members:
            name = PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or ".." in name.parts or "\\" in member.name or member.size < 0:
                raise ValueError("Unsafe archive member")
            if member.name != "manifest.json" and (not name.parts or name.parts[0] not in {"state", "workspace"}):
                raise ValueError("Unknown backup root")
        manifest_member = archive.getmember("manifest.json")
        if manifest_member.size > 20_000_000:
            raise ValueError("Manifest too large")
        manifest = json.load(archive.extractfile(manifest_member))
        if manifest.get("schema") != 1 or set(manifest.get("files", {})) != set(names) - {"manifest.json"}:
            raise ValueError("Manifest membership mismatch")
        # Verify EVERYTHING before creating the destination.
        for name, expected in manifest["files"].items():
            stream = archive.extractfile(name)
            raw = stream.read()
            if len(raw) != expected["size"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                raise ValueError("Backup content hash mismatch")
        destination.mkdir(mode=0o700, parents=True)
        for name in manifest["files"]:
            path = destination.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(archive.extractfile(name).read())
            path.chmod(0o600)
        (destination / "state").mkdir(mode=0o700, exist_ok=True)
        (destination / "workspace").mkdir(mode=0o700, exist_ok=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("create")
    backup.add_argument("--out", type=Path, required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "create":
        result = create_backup(Settings(), args.out)
    else:
        result = restore_backup(args.archive, args.destination)
    print(json.dumps({"files": len(result["files"]), "schema": result["schema"], "encrypted": False}))


if __name__ == "__main__":
    main()
