import base64
import importlib.util
import io
import json
import tarfile
from pathlib import Path
import httpx
import pytest
from devpilot.safety import SafetyError
from devpilot.tools.kubernetes import KubernetesRunner, job_manifest, snapshot_archive


def options(tmp_path):
    token = tmp_path / "service-token"
    token.write_text("private-kube-token")
    return {"runner_image": "devpilot-runner:local", "kube_namespace": "devpilot-runners",
            "kube_token_file": str(token), "kube_ca_file": str(tmp_path / "ca.crt"),
            "kube_api_url": "https://kubernetes.default.svc", "kube_job_timeout": 30}


def test_snapshot_only_contains_sanitized_files(workspace):
    (workspace.root / ".env").write_text("secret=excluded")
    value = snapshot_archive(workspace)
    with tarfile.open(fileobj=io.BytesIO(value), mode="r:gz") as archive:
        assert archive.getnames() == ["app.py"]
        assert archive.extractfile("app.py").read() == b"value = 1\n"


def test_job_has_no_credentials_network_mounts_or_model_chosen_command(tmp_path):
    job = job_manifest("test-job", options(tmp_path))
    spec = job["spec"]["template"]["spec"]
    assert not spec["automountServiceAccountToken"]
    assert not spec["enableServiceLinks"]
    assert spec["securityContext"]["runAsNonRoot"]
    container = spec["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"]
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert container["command"] == ["python", "-I", "/opt/devpilot-job.py"]
    assert "docker.sock" not in json.dumps(job)
    assert "hostPath" not in json.dumps(job)
    assert "secretKeyRef" not in json.dumps(job)
    assert job["spec"]["backoffLimit"] == 0
    assert job["spec"]["ttlSecondsAfterFinished"] == 300


@pytest.mark.parametrize("exit_code", [0, 1, 137])
def test_kubernetes_api_lifecycle_logs_exitcode_and_cleanup(tmp_path, workspace, exit_code):
    opts = options(tmp_path)
    observed = []
    uid = "created-job-uid"
    def transport(request):
        observed.append(request)
        assert request.headers["Authorization"] == "Bearer private-kube-token"
        if request.method == "POST" and request.url.path.endswith("/jobs"):
            return httpx.Response(201, json={"metadata": {"uid": uid}})
        if request.method == "POST" and request.url.path.endswith("/configmaps"):
            body = json.loads(request.content)
            assert body["immutable"]
            assert body["metadata"]["ownerReferences"][0]["uid"] == uid
            assert base64.b64decode(body["binaryData"]["snapshot.tar.gz"])
            return httpx.Response(201, json={})
        if request.url.path.endswith("/pods"):
            return httpx.Response(200, json={"items": [{"metadata": {"name": "test-pod", "ownerReferences": [{"uid": uid}]}, "status": {"containerStatuses": [{"name": "tests", "state": {"terminated": {"exitCode": exit_code}}}]}}]})
        if request.url.path.endswith("/log"):
            return httpx.Response(200, text="actual pytest output")
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        raise AssertionError(str(request.url))
    with httpx.Client(base_url=opts["kube_api_url"], transport=httpx.MockTransport(transport)) as client:
        result = KubernetesRunner(opts, client=client).run(workspace)
    assert result["exit_code"] == exit_code
    assert result["output"] == "actual pytest output"
    assert observed[-1].method == "DELETE"
    assert "private-kube-token" not in json.dumps(result)


def test_failed_create_does_not_delete_someone_elses_job(tmp_path, workspace):
    opts = options(tmp_path)
    observed = []
    def transport(request):
        observed.append(request.method)
        return httpx.Response(403, text="sensitive response")
    with httpx.Client(base_url=opts["kube_api_url"], transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(SafetyError, match="403") as error:
            KubernetesRunner(opts, client=client).run(workspace)
    assert observed == ["POST"]
    assert "sensitive response" not in str(error.value)


def test_archive_limit(workspace, monkeypatch):
    from devpilot.tools import kubernetes
    monkeypatch.setattr(kubernetes, "MAX_ARCHIVE", 1)
    with pytest.raises(SafetyError, match="700KB"):
        snapshot_archive(workspace)


def entrypoint():
    path = Path(__file__).resolve().parents[1] / "runner" / "job_entrypoint.py"
    spec = importlib.util.spec_from_file_location("job_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name,kind", [("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)])
def test_job_extractor_rejects_paths_and_links(tmp_path, name, kind):
    path = tmp_path / "input.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        item = tarfile.TarInfo(name)
        item.type = kind
        item.size = 1 if kind == tarfile.REGTYPE else 0
        archive.addfile(item, io.BytesIO(b"x") if item.size else None)
    with pytest.raises(ValueError):
        entrypoint().extract(path, tmp_path / "output")


def test_job_extractor_roundtrip(tmp_path, workspace):
    path = tmp_path / "input.tar.gz"
    path.write_bytes(snapshot_archive(workspace))
    target = tmp_path / "unpacked"
    entrypoint().extract(path, target)
    assert (target / "app.py").read_text() == "value = 1\n"
