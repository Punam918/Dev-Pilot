"""Fixed-command Kubernetes Job runner using the HTTPS Kubernetes API.

The app/terminal MCP process is trusted. Tests get neither its service-account
token, data volume, model credentials, nor network access (enforcing CNI required).
Small snapshots travel in an immutable ConfigMap owned by the ephemeral Job.
"""
from __future__ import annotations
import base64
import io
import ssl
import tarfile
import time
import uuid
from pathlib import Path

import httpx

from ..safety import MAX_REPO_BYTES, SafetyError, Workspace, redact

MAX_ARCHIVE = 700_000  # base64 expansion plus metadata stays below ConfigMap's 1MiB cap
MAX_LOG = 48_000


def snapshot_archive(workspace: Workspace) -> bytes:
    stream = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name in workspace.files():
            data = workspace.read_bytes(name)
            total += len(data)
            if total > MAX_REPO_BYTES:
                raise SafetyError("Snapshot exceeds the repository size budget")
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o444
            member.mtime = 0
            archive.addfile(member, io.BytesIO(data))
    value = stream.getvalue()
    if len(value) > MAX_ARCHIVE:
        raise SafetyError("Kubernetes runner snapshot exceeds 700KB compressed; use a smaller repository")
    return value


def job_manifest(name: str, options: dict) -> dict:
    labels = {"app.kubernetes.io/name": "devpilot-test", "devpilot/run": name}
    spec = {
        "restartPolicy": "Never", "automountServiceAccountToken": False,
        "enableServiceLinks": False, "serviceAccountName": "devpilot-runner",
        "securityContext": {"runAsNonRoot": True, "runAsUser": 65534, "runAsGroup": 65534,
                            "fsGroup": 65534, "seccompProfile": {"type": "RuntimeDefault"}},
        "containers": [{"name": "tests", "image": options["runner_image"], "imagePullPolicy": "IfNotPresent",
            "command": ["python", "-I", "/opt/devpilot-job.py"],
            "env": [{"name": "HOME", "value": "/tmp"}, {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
                    {"name": "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "value": "1"}],
            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]}},
            "resources": {"requests": {"cpu": "100m", "memory": "128Mi", "ephemeral-storage": "32Mi"},
                          "limits": {"cpu": "1", "memory": "512Mi", "ephemeral-storage": "256Mi"}},
            "volumeMounts": [{"name": "snapshot", "mountPath": "/input", "readOnly": True},
                             {"name": "work", "mountPath": "/workspace"}, {"name": "tmp", "mountPath": "/tmp"}]}],
        "volumes": [{"name": "snapshot", "configMap": {"name": name, "defaultMode": 292}},
                    {"name": "work", "emptyDir": {"medium": "Memory", "sizeLimit": "32Mi"}},
                    {"name": "tmp", "emptyDir": {"medium": "Memory", "sizeLimit": "128Mi"}}]}
    if options.get("kube_runtime_class"):
        spec["runtimeClassName"] = options["kube_runtime_class"]
    if options.get("kube_image_pull_secret"):
        spec["imagePullSecrets"] = [{"name": options["kube_image_pull_secret"]}]
    return {"apiVersion": "batch/v1", "kind": "Job",
            "metadata": {"name": name, "namespace": options["kube_namespace"], "labels": labels},
            "spec": {"backoffLimit": 0, "activeDeadlineSeconds": int(options.get("kube_job_timeout", 180)),
                     "ttlSecondsAfterFinished": 300, "template": {"metadata": {"labels": labels}, "spec": spec}}}


class KubernetesRunner:
    def __init__(self, options: dict, client: httpx.Client | None = None):
        self.options = options
        self.owned_client = client is None
        self.token_file = Path(options["kube_token_file"])
        if client is None:
            if not self.token_file.is_file():
                raise SafetyError("Kubernetes service-account token is not mounted")
            context = ssl.create_default_context(cafile=str(options["kube_ca_file"]))
            client = httpx.Client(base_url=options["kube_api_url"].rstrip("/"), verify=context,
                                  trust_env=False, follow_redirects=False, timeout=5)
        self.client = client
        self.core = f"/api/v1/namespaces/{options['kube_namespace']}"
        self.batch = f"/apis/batch/v1/namespaces/{options['kube_namespace']}"

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        # Re-read rotating projected tokens; never include them in error messages.
        token = self.token_file.read_text().strip()
        response = self.client.request(method, path, headers={"Authorization": "Bearer " + token}, **kwargs)
        if response.status_code >= 400:
            raise SafetyError(f"Kubernetes API {method} failed with HTTP {response.status_code}; check scoped RBAC, namespace, quotas, and API reachability")
        return response

    def run(self, workspace: Workspace) -> dict:
        archive = snapshot_archive(workspace)
        name = "devpilot-test-" + uuid.uuid4().hex[:16]
        created_job = False
        start = time.monotonic()
        deadline = start + int(self.options.get("kube_job_timeout", 180))
        try:
            job = self.request("POST", self.batch + "/jobs", json=job_manifest(name, self.options)).json()
            created_job = True
            snapshot = {"apiVersion": "v1", "kind": "ConfigMap", "immutable": True,
                "metadata": {"name": name, "namespace": self.options["kube_namespace"],
                             "labels": {"app.kubernetes.io/name": "devpilot-test"},
                             "ownerReferences": [{"apiVersion": "batch/v1", "kind": "Job", "name": name, "uid": job["metadata"]["uid"]}]},
                "binaryData": {"snapshot.tar.gz": base64.b64encode(archive).decode()}}
            self.request("POST", self.core + "/configmaps", json=snapshot)
            while time.monotonic() < deadline:
                pods = self.request("GET", self.core + "/pods", params={"labelSelector": "job-name=" + name}).json().get("items", [])
                for pod in pods:
                    # Do not trust an unrelated pod with only a matching label.
                    owners = pod.get("metadata", {}).get("ownerReferences", [])
                    if not any(o.get("uid") == job["metadata"]["uid"] for o in owners):
                        continue
                    for status in pod.get("status", {}).get("containerStatuses", []):
                        terminated = status.get("state", {}).get("terminated")
                        if status.get("name") != "tests" or terminated is None:
                            continue
                        pod_name = pod["metadata"]["name"]
                        raw = self.request("GET", self.core + f"/pods/{pod_name}/log",
                                params={"container": "tests", "limitBytes": MAX_LOG + 1}).content
                        return {"exit_code": terminated["exitCode"], "output": redact(raw[:MAX_LOG].decode("utf-8", "replace")),
                                "output_limited": len(raw) > MAX_LOG, "timed_out": False,
                                "duration_ms": round((time.monotonic() - start) * 1000), "job": name}
                current = self.request("GET", self.batch + "/jobs/" + name).json()
                failed = any(c.get("type") == "Failed" and c.get("status") == "True" for c in current.get("status", {}).get("conditions", []))
                if failed:
                    return {"exit_code": -1, "output": "Job failed before a test exit status was available; inspect namespace events.",
                            "timed_out": False, "output_limited": False, "job": name,
                            "duration_ms": round((time.monotonic() - start) * 1000)}
                time.sleep(.5)
            return {"exit_code": -1, "output": "Job exceeded its scheduling/execution deadline.",
                    "timed_out": True, "output_limited": False, "job": name,
                    "duration_ms": round((time.monotonic() - start) * 1000)}
        finally:
            if created_job:
                try:
                    self.request("DELETE", self.batch + "/jobs/" + name,
                                 json={"propagationPolicy": "Background"})
                except (httpx.HTTPError, SafetyError, OSError):
                    # Job TTL and ownerReferences provide eventual cleanup. Cancellation
                    # can kill this subprocess before finally; activeDeadline still applies.
                    pass
            if self.owned_client:
                self.client.close()
