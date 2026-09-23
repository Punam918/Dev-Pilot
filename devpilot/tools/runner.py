"""Fixed pytest runner. A test suite is arbitrary code, not a read-only action."""
from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

from ..process import run_process
from ..safety import SafetyError, Workspace

PYTEST_ARGS = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-o", "pythonpath=.", "tests"]


def docker_command(root: Path, image: str, name: str) -> list[str]:
    # All Docker options come from trusted application code, never model text.
    # Avoid comma-containing host paths, which Docker's --mount grammar splits.
    if "," in str(root):
        raise SafetyError("Docker workspace paths cannot contain commas")
    return ["docker", "run", "--rm", "--name", name, "--pull=never",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "128",
            "--memory", "512m", "--cpus", "1", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m", "--workdir", "/workspace",
            "--mount", f"type=bind,source={root},target=/workspace,readonly",
            "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "--entrypoint", "python", image, *PYTEST_ARGS]


def run_tests(workspace: Workspace, options: dict) -> dict:
    mode = options.get("runner", "disabled")
    if mode == "disabled":
        raise SafetyError("Test execution is disabled. Choose Docker, or explicitly trust local demo code")
    if not workspace.path("tests").is_dir():
        raise SafetyError("This runner requires a Python project with a tests/ directory")
    before = workspace.fingerprint()
    timeout = int(options.get("tool_timeout", 90))
    if mode == "host-trusted":
        if not options.get("trust_local_code"):
            raise SafetyError("Host code execution was not explicitly authorized by the operator")
        result = run_process([sys.executable, *PYTEST_ARGS], workspace.root, timeout=timeout)
    elif mode == "docker":
        if not shutil.which("docker"):
            raise SafetyError("Docker CLI is unavailable. Run the backend on your development host")
        name = f"devpilot-test-{uuid.uuid4().hex[:12]}"
        try:
            result = run_process(docker_command(workspace.root,
                                 options.get("runner_image", "devpilot-runner:local"), name),
                                 workspace.root, timeout=timeout)
        finally:
            # Delete only the exact ephemeral container this call created.
            run_process(["docker", "rm", "--force", name], workspace.root, timeout=10)
    elif mode == "kubernetes":
        from .kubernetes import KubernetesRunner
        result = KubernetesRunner(options).run(workspace)
    else:
        raise SafetyError("Unknown runner mode")
    return {**result, "runner": mode, "command": "python " + " ".join(PYTEST_ARGS),
            "snapshot_sha256": before, "snapshot_unchanged": before == workspace.fingerprint()}
