"""Operator-controlled configuration. Model output cannot change these settings."""
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DP_", env_file=".env", extra="ignore")
    provider: Literal["demo", "openai"] = "demo"
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3:4b"
    llm_api_key: str = "local"
    allow_remote_model: bool = False
    api_token: str = ""
    workspace_dir: Path = Path("workspace")
    data_dir: Path = Path(".devpilot")
    runner: Literal["disabled", "host-trusted", "docker", "kubernetes"] = "disabled"
    trust_local_code: bool = False
    runner_image: str = "devpilot-runner:local"
    docker_tools: bool = False
    docker_label: str = "devpilot.scope=demo"
    max_steps: int = Field(default=24, ge=1, le=50)
    max_tool_calls: int = Field(default=40, ge=1, le=100)
    max_context_chars: int = Field(default=90000, ge=1000, le=250000)
    tool_timeout: int = Field(default=90, ge=1, le=300)
    llm_timeout: int = Field(default=120, ge=1, le=600)
    approval_timeout: int = Field(default=300, ge=1, le=1800)
    run_timeout: int = Field(default=1200, ge=10, le=3600)
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1024, le=65535)
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    max_runs: int = Field(default=100, ge=1, le=10000)

    # Deployment settings are operator-controlled, never model arguments.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "[::1]", "testserver"]
    pod_ip: str = ""  # Downward API; permits authenticated ServiceMonitor scrapes to the Pod IP.
    public_origin: str = ""
    metrics_token: str = ""
    metrics_token_file: Path | None = None
    api_token_file: Path | None = None
    otel_enabled: bool = False
    otel_endpoint: str = "http://127.0.0.1:4318/v1/traces"
    log_json: bool = True
    kube_api_url: str = "https://kubernetes.default.svc"
    kube_namespace: str = "devpilot-runners"
    kube_token_file: Path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
    kube_ca_file: Path = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
    kube_runtime_class: str = ""
    kube_image_pull_secret: str = ""
    kube_job_timeout: int = Field(default=180, ge=30, le=270)

    @model_validator(mode="after")
    def validate_configuration(self):
        import re
        for name in ("api_token", "metrics_token"):
            path = getattr(self, name + "_file")
            if path:
                value = path.read_text().strip()
                if not value:
                    raise ValueError(f"{name}_file is empty")
                setattr(self, name, value)
        if self.metrics_token and self.metrics_token == self.api_token:
            raise ValueError("API and metrics credentials must be different")
        if self.metrics_token and len(self.metrics_token) < 24:
            raise ValueError("DP_METRICS_TOKEN must contain at least 24 characters")
        if self.pod_ip:
            from ipaddress import ip_address
            address = str(ip_address(self.pod_ip))
            if address not in self.allowed_hosts:
                self.allowed_hosts = [*self.allowed_hosts, address]
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            raise ValueError("Set explicit DP_ALLOWED_HOSTS; wildcard is not accepted")
        if self.public_origin:
            parsed = urlparse(self.public_origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.username or parsed.query or parsed.fragment:
                raise ValueError("DP_PUBLIC_ORIGIN must be an exact HTTP(S) origin")
            self.public_origin = self.public_origin.rstrip("/")
        if self.runner == "kubernetes":
            parsed = urlparse(self.kube_api_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.path not in {"", "/"}:
                raise ValueError("Kubernetes API must be HTTPS without credentials or a path")
            if not re.fullmatch(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?", self.kube_namespace):
                raise ValueError("Invalid runner namespace")
            if self.tool_timeout < self.kube_job_timeout + 15:
                raise ValueError("Set DP_TOOL_TIMEOUT >= DP_KUBE_JOB_TIMEOUT + 15")
        if self.otel_enabled:
            parsed = urlparse(self.otel_endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                raise ValueError("DP_OTEL_ENDPOINT must be an HTTP(S) OTLP traces URL")
        if self.runner == "host-trusted" and not self.trust_local_code:
            raise ValueError("host-trusted executes code on this computer; set DP_TRUST_LOCAL_CODE=true explicitly")
        url = urlparse(self.base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username:
            raise ValueError("DP_BASE_URL must be an HTTP(S) URL without embedded credentials")
        local = {"localhost", "127.0.0.1", "::1", "ollama", "vllm", "host.docker.internal"}
        if self.provider == "openai" and url.hostname not in local and not self.allow_remote_model:
            raise ValueError("Remote inference requires DP_ALLOW_REMOTE_MODEL=true; repository data will leave this host")
        if self.api_token and len(self.api_token) < 24:
            raise ValueError("DP_API_TOKEN must contain at least 24 characters")
        self.workspace_dir = self.workspace_dir.expanduser().resolve()
        self.data_dir = self.data_dir.expanduser().resolve()
        if self.workspace_dir == self.data_dir or self.data_dir.is_relative_to(self.workspace_dir):
            raise ValueError("DP_DATA_DIR must be outside DP_WORKSPACE_DIR")
        return self
