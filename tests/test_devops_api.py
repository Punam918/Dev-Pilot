import json
import logging
import pytest
from fastapi.testclient import TestClient
from devpilot.api import create_app
from devpilot.config import Settings
from devpilot.lease import InstanceLease
from devpilot.telemetry import JsonFormatter, Telemetry


def test_health_readiness_and_separate_metrics_credentials(config):
    config.metrics_token = "metrics-only-abcdefghijklmnopqrstuvwxyz"
    with TestClient(create_app(config)) as client:
        assert client.get("/livez").json()["status"] == "ok"
        assert client.get("/readyz").status_code == 200
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer " + config.api_token}).status_code == 401
        text = client.get("/metrics", headers={"Authorization": "Bearer " + config.metrics_token}).text
        assert "devpilot_active_runs" in text
        assert config.api_token not in text
        assert "demo-redis" not in text


def test_metrics_disabled_without_token(config):
    with TestClient(create_app(config)) as client:
        assert client.get("/metrics").status_code == 404


def test_drain_pauses_new_runs_not_reads_and_resume(config):
    with TestClient(create_app(config)) as client:
        headers = {"Authorization": "Bearer " + config.api_token}
        assert client.post("/api/admin/drain").status_code == 401
        assert client.post("/api/admin/drain", headers=headers).json()["draining"]
        assert client.get("/readyz").status_code == 503
        assert client.get("/livez").status_code == 200
        assert client.get("/api/repos", headers=headers).status_code == 200
        assert client.post("/api/runs", json={"repo": "demo-redis", "task": "fix"}, headers=headers).status_code == 503
        assert client.post("/api/admin/resume", headers=headers).status_code == 200
        assert client.get("/readyz").status_code == 200


def test_explicit_ingress_host_and_external_origin(config):
    config.allowed_hosts = ["testserver", "devpilot.example"]
    config.public_origin = "https://devpilot.example"
    headers = {"Host": "devpilot.example", "Origin": "https://devpilot.example", "Authorization": "Bearer " + config.api_token}
    with TestClient(create_app(config)) as client:
        assert client.post("/api/admin/drain", headers=headers).status_code == 200
        assert client.post("/api/admin/resume", headers={**headers, "Origin": "https://evil.example"}).status_code == 403
        assert client.get("/livez", headers={"Host": "evil.example"}).status_code == 400


def test_singleton_lease_blocks_second_instance(tmp_path):
    with InstanceLease(tmp_path):
        with pytest.raises(RuntimeError, match="already"):
            with InstanceLease(tmp_path):
                pass
    with InstanceLease(tmp_path):
        pass


def test_token_files_and_config_constraints(tmp_path):
    token = tmp_path / "token"
    token.write_text("abcdefghijklmnopqrstuvwxyz0123456789\n")
    metrics = tmp_path / "metrics-token"
    metrics.write_text("different-metrics-token-abcdefghijklmnopqrstuvwxyz\n")
    settings = Settings(_env_file=None, api_token_file=token, metrics_token_file=metrics)
    assert settings.api_token == token.read_text().strip()
    assert settings.metrics_token == metrics.read_text().strip()
    with pytest.raises(ValueError):
        Settings(_env_file=None, api_token_file=token, metrics_token_file=token)
    with pytest.raises(ValueError):
        Settings(_env_file=None, allowed_hosts=["*"])
    with pytest.raises(ValueError):
        Settings(_env_file=None, public_origin="https://host/path")
    with pytest.raises(ValueError):
        Settings(_env_file=None, runner="kubernetes", tool_timeout=90)
    with pytest.raises(ValueError):
        Settings(_env_file=None, runner="kubernetes", tool_timeout=240, kube_namespace="../bad")
    settings = Settings(_env_file=None, runner="kubernetes", tool_timeout=240)
    assert settings.kube_job_timeout == 180


def test_metric_labels_bound_tool_names_and_preserve_missing_usage():
    from prometheus_client import generate_latest
    telemetry = Telemetry()
    telemetry.event("tool_result", {"tool": "private/path/token", "ok": False})
    telemetry.event("model_result", {"duration_ms": 15, "usage": {}})
    telemetry.event("approval_required", {})
    telemetry.event("approval_decision", {"approved": False})
    telemetry.event("run_started", {})
    telemetry.event("run_finished", {"status": "completed", "metrics": {"wall_ms": 100}})
    text = generate_latest(telemetry.registry).decode()
    assert 'tool="unknown"' in text and "private/path/token" not in text
    assert "devpilot_model_tokens_total{" not in text
    assert 'decision="denied"' in text


def test_operational_logging_does_not_serialize_arbitrary_extras():
    record = logging.LogRecord("devpilot.operations", 20, "file.py", 1, "http_response", (), None)
    record.api_token = "never-log-this"
    record.route = "/api/runs/{run_id}"
    result = JsonFormatter().format(record)
    assert "never-log-this" not in result
    assert json.loads(result)["route"] == "/api/runs/{run_id}"


def test_unmatched_routes_are_not_high_cardinality(config):
    from prometheus_client import generate_latest
    with TestClient(create_app(config)) as client:
        client.get("/secret-url-1234?api_key=do-not-log")
        text = generate_latest(client.app.state.manager.telemetry.registry).decode()
        assert 'route="unmatched"' in text
        assert "secret-url-1234" not in text
        assert "do-not-log" not in text


def test_downward_api_host_is_validated(tmp_path):
    cfg = Settings(_env_file=None, data_dir=tmp_path/"state", workspace_dir=tmp_path/"repo", pod_ip="10.244.0.8")
    assert "10.244.0.8" in cfg.allowed_hosts
    with pytest.raises(ValueError):
        Settings(_env_file=None, data_dir=tmp_path/"bad", workspace_dir=tmp_path/"repo", pod_ip="evil.example")
