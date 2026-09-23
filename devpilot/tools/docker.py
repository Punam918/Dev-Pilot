"""Optional, label-scoped Docker observations. No daemon mutation tools exist."""
import json
import re
from pathlib import Path

from ..process import run_process
from ..safety import SafetyError, redact


def command(args: list[str], root: Path) -> str:
    result = run_process(["docker", *args], root, timeout=15, max_output=25000, sanitize=False)
    if result["exit_code"] != 0 or result["output_limited"]:
        raise SafetyError("Docker observation failed or exceeded the output budget")
    return result["output"]


def check_enabled(options: dict) -> None:
    if not options.get("docker_tools") or not options.get("docker_label"):
        raise SafetyError("Docker observation is disabled or lacks an explicit label scope")


def list_containers(root: Path, options: dict) -> dict:
    check_enabled(options)
    output = command(["ps", "--all", "--filter", f"label={options['docker_label']}",
                      "--format", "{{json .}}"], root)
    return {"scope": options["docker_label"], "containers": [json.loads(line) for line in output.splitlines() if line]}


def inspect_container(root: Path, options: dict, container_id: str) -> dict:
    check_enabled(options)
    if not re.fullmatch(r"[a-fA-F0-9]{12,64}", container_id):
        raise SafetyError("Use a Docker container ID returned by list_containers")
    item = json.loads(command(["inspect", "--type", "container", container_id], root))[0]
    key, _, value = options["docker_label"].partition("=")
    labels = item.get("Config", {}).get("Labels") or {}
    if key not in labels or (value and labels[key] != value):
        raise SafetyError("Container is outside the approved label scope")
    state = item.get("State", {})
    # Never return Config.Env, mounts, credentials, or complete inspect output.
    return {"id": item["Id"], "name": item["Name"], "status": state.get("Status"),
            "exit_code": state.get("ExitCode"), "running": state.get("Running"),
            "health": state.get("Health", {}).get("Status", "not configured")}


def logs(root: Path, options: dict, container_id: str) -> dict:
    inspect_container(root, options, container_id)
    return {"container_id": container_id,
            "logs": redact(command(["logs", "--tail", "100", container_id], root))}
