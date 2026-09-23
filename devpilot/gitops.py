"""Git operates on fresh snapshot metadata, never the source repository's .git."""
from pathlib import Path
from .process import run_process


def git(root: Path, args: list[str]) -> dict:
    return run_process(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgSign=false",
                        "-c", "core.fsmonitor=false", "-c", "diff.external=", *args], root, timeout=30, sanitize=False)


def initialize(root: Path) -> None:
    commands = [["init", "--initial-branch=main"], ["add", "--all", "--force"],
                ["-c", "user.name=DevPilot Snapshot", "-c", "user.email=snapshot@localhost",
                 "commit", "--allow-empty", "-m", "Immutable input snapshot"]]
    for args in commands:
        result = git(root, args)
        if result["exit_code"] != 0:
            raise RuntimeError(f"Cannot initialize snapshot Git repository: {result['output']}")


def diff(root: Path) -> str:
    result = git(root, ["diff", "--no-ext-diff", "--no-textconv", "HEAD", "--"])
    if result["exit_code"] != 0 or result["output_limited"]:
        raise RuntimeError("Unable to produce a complete bounded patch")
    return result["output"]
