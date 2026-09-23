#!/usr/bin/env python3
"""Build a clean source archive with a SHA-256 manifest; never package local state."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", ".devpilot", "__pycache__", ".pytest_cache", ".ruff_cache",
                 "build", "dist", "node_modules", "htmlcov", ".secrets", "backups", ".terraform", "release"}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in relative.parts):
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    if path.name == "BUILD_INFO.local.json" or path.name.endswith((".tfvars", ".tfvars.json", ".tfstate", ".tfstate.backup", ".tfplan")):
        return False
    if path.name in {".coverage", "coverage.xml", "MANIFEST.sha256"} or path.suffix in {".pyc", ".pyo"}:
        return False
    if relative.parts[0] == "workspace" and path.name != ".gitkeep":
        return False
    if relative.parts[0] == "outputs" and len(relative.parts) > 1 and relative.parts[1].startswith(("local-", "live-")):
        return False
    return path.is_file() and not path.is_symlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT.parent / "devpilot-devops-complete.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("Write the archive outside the source directory")
    files = sorted(path for path in ROOT.rglob("*") if included(path))
    manifest = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}\n" for path in files)
    (ROOT / "MANIFEST.sha256").write_text(manifest)
    files.append(ROOT / "MANIFEST.sha256")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            entry = zipfile.ZipInfo("devpilot/" + relative, date_time=(2026, 9, 16, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if path.name.endswith(".sh") else 0o100644) << 16
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError("Corrupt member: " + bad)
    print(f"Created {output} with {len(files)} files ({output.stat().st_size:,} bytes)")
    print("SHA256:", hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
