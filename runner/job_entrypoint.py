"""Trusted Job image entrypoint: bounded extraction and a fixed pytest command.

Tests have no API token/network/data volume. This is not a hostile-code VM.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath


def extract(source: Path, target: Path) -> None:
    total = 0
    with tarfile.open(source, "r:gz") as archive:
        for count, member in enumerate(archive, 1):
            name = PurePosixPath(member.name)
            if count > 1500 or not member.isfile() or name.is_absolute() or ".." in name.parts or not name.parts or "\\" in member.name:
                raise ValueError("Invalid snapshot member")
            if member.size > 120_000 or member.size < 0:
                raise ValueError("File exceeds the allowed size")
            total += member.size
            if total > 12_000_000:
                raise ValueError("Snapshot exceeds the unpacked budget")
            destination = target.joinpath(*name.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise ValueError("Duplicate snapshot member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing file data")
            with destination.open("xb") as output:
                output.write(stream.read(120_001))
            destination.chmod(0o444)


def main():
    root = Path("/workspace")
    extract(Path("/input/snapshot.tar.gz"), root)
    # A fixed argument list; the model cannot choose commands, image, or mounts.
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-o", "pythonpath=.", "tests"]
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": "/tmp",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONHASHSEED": "0"}
    # Exit status comes from the container status, not text the model can invent.
    result = subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
