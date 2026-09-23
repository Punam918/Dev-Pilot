"""Opt-in real Docker check. Skipped, never represented as passed, without Docker."""
import os
import pytest
from devpilot.safety import Workspace, copy_workspace
from devpilot.demo import FIXTURES, CASES
from devpilot.safety import digest
from devpilot.tools.runner import run_tests

pytestmark = [pytest.mark.docker, pytest.mark.skipif(os.getenv("DP_TEST_DOCKER") != "1", reason="Set DP_TEST_DOCKER=1 after building devpilot-runner:local")]


def test_actual_docker_runner_before_and_after(tmp_path):
    # Docker uses uid 65534; make mount contents readable inside its namespace.
    root = tmp_path / "project"
    copy_workspace(FIXTURES / "redis", root)
    workspace = Workspace(root)
    options = {"runner": "docker", "runner_image": "devpilot-runner:local", "tool_timeout": 90}
    assert run_tests(workspace, options)["exit_code"] == 1
    case = CASES["redis"]
    workspace.replace(case["path"], case["old"], case["new"], digest(workspace.read(case["path"])))
    after = run_tests(workspace, options)
    assert after["exit_code"] == 0
    assert after["snapshot_unchanged"]
