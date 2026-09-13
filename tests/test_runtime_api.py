import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from devpilot.api import create_app
from devpilot.runtime import RunManager, BusyError
from devpilot.safety import Workspace, SafetyError
from devpilot.models import Reply, ToolCall
from devpilot.store import Store
from devpilot.config import Settings


async def drive(manager, run_id, approve=True):
    while manager.active and not manager.active.done():
        run = manager.store.get(run_id)
        pending = run.get("pending_approval")
        if pending:
            try:
                manager.decide(run_id, pending["id"], approve)
            except KeyError:
                pass
        await asyncio.sleep(.05)
    await manager.active
    return manager.store.get(run_id)


async def test_end_to_end_actual_mcp_fix_and_pytest(config):
    manager = RunManager(config)
    original = Workspace(config.workspace_dir / "demo-redis").fingerprint()
    identifier = manager.create("demo-redis", "Fix Redis")
    run = await drive(manager, identifier)
    assert run["status"] == "completed"
    assert run["verification"]["verified"] is True
    assert run["verification"]["source_unchanged"] is True
    assert Workspace(config.workspace_dir / "demo-redis").fingerprint() == original
    events = manager.store.events(identifier)
    executions = [e["data"]["result"] for e in events if e["kind"] == "tool_result" and e["data"]["tool"] == "terminal__run_tests"]
    assert [x["exit_code"] for x in executions] == [1, 0]
    assert len([e for e in events if e["kind"] == "approval_decision"]) == 3
    assert run["metrics"]["prompt_tokens"] is None
    assert (config.data_dir / "runs" / identifier / "changes.patch").read_text().startswith("diff --git")


async def test_approval_denial_means_no_edit_and_no_false_verification(config):
    manager = RunManager(config)
    identifier = manager.create("demo-redis", "Fix Redis")
    run = await drive(manager, identifier, approve=False)
    assert not run["verification"]["verified"]
    assert not run["verification"]["tests_executed"]
    assert not run["patch_available"]


async def test_diagnose_mode_removes_edit_capability(config):
    manager = RunManager(config)
    identifier = manager.create("demo-redis", "Diagnose only", "diagnose")
    run = await drive(manager, identifier)
    assert not run["patch_available"]
    assert run["verification"]["last_exit_code"] == 1


async def test_busy_run_cancel_and_approval_binding(config):
    manager = RunManager(config)
    identifier = manager.create("demo-redis", "Fix")
    with pytest.raises(BusyError):
        manager.create("demo-redis", "another")
    with pytest.raises(KeyError):
        manager.decide("wrong-run", "made-up-approval", True)
    # Let the run start so cancellation follows the normal teardown path.
    await asyncio.sleep(.1)
    await manager.cancel(identifier)
    assert manager.store.get(identifier)["status"] == "cancelled"


def test_server_auth_origin_and_request_validation(config):
    with TestClient(create_app(config)) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/repos").status_code == 401
        headers = {"Authorization": f"Bearer {config.api_token}"}
        assert "demo-redis" in client.get("/api/repos", headers=headers).json()["repositories"]
        assert "api_token" not in client.get("/api/config", headers=headers).text
        assert client.post("/api/runs", json={"repo": "../", "task": "x"}, headers=headers).status_code == 400
        assert client.post("/api/runs", json={"repo": "demo-redis", "task": "x", "shell": "anything"}, headers=headers).status_code == 422
        assert client.post("/api/runs", json={"repo": "demo-redis", "task": "x"}, headers={**headers, "Origin": "https://attacker.invalid"}).status_code == 403
        assert client.get("/api/runs/missing", headers=headers).status_code == 404
        assert client.get("/").status_code == 200
        assert "Content-Security-Policy" in client.get("/").headers


def test_restart_marks_unfinished_runs_interrupted(config):
    store = Store(config.data_dir / "audit.sqlite3")
    store.create("unfinished", {"repo": "demo-redis"})
    store.update("unfinished", status="awaiting_approval")
    manager = RunManager(config)
    assert manager.store.get("unfinished")["status"] == "interrupted"


@pytest.mark.parametrize("path", ["/", "/static/style.css", "/static/app.js", "/api/config"])
def test_browser_responses_are_not_cached(config, path):
    with TestClient(create_app(config)) as client:
        response = client.get(path, headers={"Authorization": f"Bearer {config.api_token}"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["expires"] == "0"


def test_modified_fixture_cannot_enter_scripted_demo(config):
    (config.workspace_dir / "demo-redis" / "evil.py").write_text("raise RuntimeError('not bundled')")
    with pytest.raises(SafetyError):
        RunManager(config).create("demo-redis", "Fix")


def test_host_trust_and_remote_endpoint_require_explicit_configuration(tmp_path):
    with pytest.raises(ValueError):
        Settings(_env_file=None, runner="host-trusted", trust_local_code=False)
    with pytest.raises(ValueError):
        Settings(_env_file=None, provider="openai", base_url="https://remote.invalid/v1", allow_remote_model=False)


async def test_cancel_before_task_has_started(config):
    manager = RunManager(config)
    identifier = manager.create("demo-redis", "Fix")
    await manager.cancel(identifier)
    assert manager.store.get(identifier)["status"] == "cancelled"
    assert not manager.approvals


def test_http_run_approval_download_and_completed_sse(config):
    import time
    with TestClient(create_app(config)) as client:
        headers = {"Authorization": f"Bearer {config.api_token}"}
        response = client.post("/api/runs", headers=headers,
                               json={"repo": "demo-redis", "task": "Fix Redis and validate", "mode": "repair"})
        assert response.status_code == 202
        identifier = response.json()["id"]
        assert client.get(f"/api/runs/{identifier}/artifacts/patch", headers=headers).status_code == 409
        decisions = 0
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            run = client.get(f"/api/runs/{identifier}", headers=headers).json()
            pending = run.get("pending_approval")
            if pending:
                path = f"/api/runs/{identifier}/approvals/{pending['id']}"
                assert client.post(path, headers=headers, json={"approved": True}).status_code == 200
                assert client.post(path, headers=headers, json={"approved": True}).status_code == 409
                decisions += 1
            if run["status"] in {"completed", "failed", "cancelled", "limit_reached"}:
                break
            time.sleep(.05)
        assert run["status"] == "completed", run
        assert run["verification"]["verified"] and decisions == 3
        # Final status and file export occur consecutively on the same event loop.
        patch = client.get(f"/api/runs/{identifier}/artifacts/patch", headers=headers)
        assert patch.status_code == 200 and "diff --git" in patch.text
        assert "localhost" in patch.text and "redis" in patch.text
        trace = client.get(f"/api/runs/{identifier}/artifacts/trace", headers=headers).json()
        assert trace["run"]["verification"]["verified"]
        events = client.get(f"/api/runs/{identifier}/events", headers=headers)
        assert "event: trace" in events.text and "event: done" in events.text
        assert client.get("/api/model/health", headers=headers).json()["available"]
