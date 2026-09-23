"""Bounded-cardinality metrics and opt-in metadata-only OTLP spans.

No repository paths, prompts, outputs, arguments, credentials, or run IDs are
exported as labels or span attributes. The private audit DB holds tool evidence.
"""
from __future__ import annotations
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client import GCCollector, PlatformCollector, ProcessCollector

from . import __version__

TOOLS = frozenset({"files__list_files", "files__read_file", "files__replace_text",
    "git__status", "git__diff", "git__history", "docs__search", "terminal__run_tests",
    "database__schema", "database__query", "docker__list_containers", "docker__inspect", "docker__logs"})
STATUSES = frozenset({"completed", "failed", "cancelled", "interrupted", "limit_reached"})
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Only explicitly attached operational fields; never arbitrary extra data.
        value = {"time": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                 "service": "devpilot", "event": record.getMessage()}
        for key in ("request_id", "route", "method", "status", "duration_ms"):
            if hasattr(record, key):
                value[key] = getattr(record, key)
        return json.dumps(value, ensure_ascii=True)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("devpilot.operations")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


class Telemetry:
    def __init__(self, settings=None):
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        def counter(name, description, labels=()):
            return Counter("devpilot_" + name, description, labels, registry=self.registry)
        def gauge(name, description):
            return Gauge("devpilot_" + name, description, registry=self.registry)
        def hist(name, description, labels=(), buckets=(.01, .05, .1, .5, 1, 5, 15, 60, 180, 600)):
            return Histogram("devpilot_" + name, description, labels, buckets=buckets, registry=self.registry)
        self.http = counter("http_requests_total", "HTTP responses by route template", ("method", "route", "status"))
        self.http_duration = hist("http_request_duration_seconds", "HTTP time to response headers; SSE body excluded", ("method", "route"))
        self.runs = counter("runs_total", "Finished runs; demo is not AI quality", ("provider", "status", "verified"))
        self.run_duration = hist("run_duration_seconds", "Wall time including approval waits", ("provider", "status"))
        self.tools = counter("tool_calls_total", "Tool results, including denials and invalid calls", ("tool", "outcome"))
        self.tool_duration = hist("tool_duration_seconds", "Executed tool duration", ("tool",))
        self.llm_duration = hist("model_request_duration_seconds", "Model calls, separate from demo", ("provider",))
        self.tokens = counter("model_tokens_total", "Provider-reported tokens only; absent usage is not fabricated", ("provider", "kind"))
        self.approvals = counter("approvals_total", "Approval decisions", ("decision",))
        self.active = gauge("active_runs", "Currently active runs (0 or 1)")
        self.pending = gauge("pending_approvals", "Currently waiting approvals")
        self.accepting = gauge("accepting_runs", "0 while draining")
        self.ready = gauge("ready", "Last storage/application readiness check")
        self.accepting.set(1)
        self.ready.set(1)
        self.provider = getattr(settings, "provider", "demo")
        self.tracer = None
        self.tracer_provider = None
        if settings and settings.otel_enabled:
            try:
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            except ImportError as exc:
                raise RuntimeError("Install .[observability] to enable OTLP tracing") from exc
            self.tracer_provider = TracerProvider(resource=Resource.create({"service.name": "devpilot", "service.version": __version__}))
            self.tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint, timeout=3)))
            self.tracer = self.tracer_provider.get_tracer("devpilot")

    @contextmanager
    def span(self, name: str, **attributes):
        if self.tracer is None:
            yield None
        else:
            # Export only a fixed operational vocabulary, even if a future caller
            # accidentally passes source text or a model-generated unknown tool.
            safe = {}
            vocab = {"provider": {"demo", "openai"}, "tool": TOOLS, "method": METHODS}
            for key, allowed in vocab.items():
                if key in attributes:
                    value = attributes[key]
                    safe[key] = value if isinstance(value, str) and value in allowed else "unknown"
            name = name if name in {"http.request", "model.complete", "mcp.tool"} else "operation"
            # Deliberately do not export exception messages, which can contain data.
            with self.tracer.start_as_current_span(name, attributes=safe,
                    record_exception=False, set_status_on_exception=False) as span:
                try:
                    yield span
                except BaseException:
                    from opentelemetry.trace import Status, StatusCode
                    span.set_status(Status(StatusCode.ERROR))
                    raise

    def event(self, kind: str, data: dict):
        if kind == "run_started":
            self.active.set(1)
        elif kind == "run_finished":
            self.active.set(0)
            self.pending.set(0)
            status = data.get("status", "failed")
            status = status if status in STATUSES else "failed"
            verified = str(bool(data.get("verification", {}).get("verified"))).lower()
            self.runs.labels(self.provider, status, verified).inc()
            self.run_duration.labels(self.provider, status).observe(data.get("metrics", {}).get("wall_ms", 0) / 1000)
        elif kind == "approval_required":
            self.pending.set(1)
        elif kind in {"approval_decision", "approval_expired"}:
            self.pending.set(0)
            decision = "expired" if kind == "approval_expired" else ("approved" if data.get("approved") else "denied")
            self.approvals.labels(decision).inc()
        elif kind == "tool_result":
            name = data.get("tool", "unknown")
            name = name if name in TOOLS else "unknown"
            self.tools.labels(name, "ok" if data.get("ok") else "error").inc()
            if isinstance(data.get("duration_ms"), (int, float)):
                self.tool_duration.labels(name).observe(max(0, data["duration_ms"]) / 1000)
        elif kind == "model_result":
            self.llm_duration.labels(self.provider).observe(max(0, data.get("duration_ms", 0)) / 1000)
            for name in ("prompt_tokens", "completion_tokens"):
                value = data.get("usage", {}).get(name)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    self.tokens.labels(self.provider, name).inc(value)

    def close(self):
        if self.tracer_provider:
            self.tracer_provider.shutdown()
