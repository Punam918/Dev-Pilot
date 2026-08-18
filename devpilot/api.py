"""Local, bearer-authenticated API and a dependency-free browser UI."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import secrets
import logging
import time
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .config import Settings
from .runtime import RunManager, BusyError, DrainingError, TERMINAL_STATES
from .lease import InstanceLease
from .telemetry import METHODS
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .safety import SafetyError


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str = Field(min_length=1, max_length=80)
    task: str = Field(min_length=1, max_length=4000)
    mode: str = Field(default="repair", pattern="^(diagnose|repair)$")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approved: bool


def ensure_token(settings: Settings) -> str:
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings.data_dir.chmod(0o700)
    path = settings.data_dir / "access-token"
    if settings.api_token:
        return settings.api_token
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(32))
    value = path.read_text().strip()
    if len(value) < 24:
        raise ValueError("Stored API token is invalid")
    return value


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    token = ensure_token(config)
    manager = RunManager(config, recover=False)

    @asynccontextmanager
    async def lifespan(app):
        with InstanceLease(config.data_dir):
            manager.store.interrupt_unfinished()
            try:
                yield
            finally:
                await manager.shutdown()
                manager.telemetry.close()

    app = FastAPI(title="Dev-Pilot", version=__version__, lifespan=lifespan,
                  description="Local development agent. One worker and one active run. Single-operator service; place behind a private network or authenticated TLS gateway.")
    app.state.manager = manager
    app.state.config = config
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            expected = config.public_origin or f"{request.url.scheme}://{request.headers.get('host')}"
            if origin and origin != expected:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Cross-origin mutations are not accepted"}, status_code=403)
            length = request.headers.get("content-length", "0")
            if not length.isdigit() or int(length) > 12000:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Request body is too large"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        # Apply to the document and assets as well as API responses so every
        # deployment is picked up on normal navigation/reload, without a hard refresh.
        if request.url.path == "/" or request.url.path.startswith(("/static/", "/api")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.middleware("http")
    async def observe(request: Request, call_next):
        tick = time.monotonic()
        request_id = secrets.token_hex(12)
        status = 500
        route = "unmatched"
        method = request.method if request.method in METHODS else "OTHER"
        with manager.telemetry.span("http.request", method=method) as span:
            try:
                response = await call_next(request)
                status = response.status_code
                response.headers["X-Request-ID"] = request_id
                return response
            finally:
                matched = request.scope.get("route")
                if matched and hasattr(matched, "path"):
                    route = matched.path
                elif request.url.path.startswith("/static/"):
                    route = "/static/*"
                duration = time.monotonic() - tick
                if route not in {"/healthz", "/livez", "/readyz", "/metrics"}:
                    manager.telemetry.http.labels(method, route, str(status)).inc()
                    manager.telemetry.http_duration.labels(method, route).observe(duration)
                    logging.getLogger("devpilot.operations").info("http_response", extra={
                        "request_id": request_id, "route": route, "method": method,
                        "status": status, "duration_ms": round(duration * 1000, 2)})
                if span:
                    span.set_attribute("http.route", route)
                    span.set_attribute("http.response.status_code", status)

    async def authorize(request: Request):
        supplied = request.headers.get("authorization", "")
        expected = f"Bearer {token}"
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(401, "Supply the local bearer token. Run: python -m devpilot token")

    auth = [Depends(authorize)]

    def get_run(run_id: str):
        try:
            return manager.store.get(run_id)
        except KeyError:
            raise HTTPException(404, "Run not found") from None

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(static / "index.html")

    @app.get("/livez")
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__, "checks": "application process only"}

    @app.get("/readyz")
    async def readyz():
        # A model outage is not a reason to restart a healthy API process.
        healthy = not manager.draining
        try:
            with manager.store.connect() as db:
                db.execute("SELECT 1").fetchone()
            healthy = healthy and os.access(config.data_dir, os.W_OK)
        except (sqlite3.Error, OSError):
            healthy = False
        manager.telemetry.ready.set(int(healthy))
        return JSONResponse({"ready": healthy, "draining": manager.draining}, status_code=200 if healthy else 503)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request):
        if not config.metrics_token:
            raise HTTPException(404, "Metrics endpoint not configured")
        expected = "Bearer " + config.metrics_token
        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), expected.encode()):
            raise HTTPException(401, "Metrics token required")
        return Response(generate_latest(manager.telemetry.registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    @app.post("/api/admin/drain", dependencies=auth)
    async def drain():
        manager.drain()
        return {"draining": True, "active_run": manager.active_id if manager.active and not manager.active.done() else None}

    @app.post("/api/admin/resume", dependencies=auth)
    async def resume():
        manager.resume()
        return {"draining": False}

    @app.get("/api/config", dependencies=auth)
    async def public_config():
        return {"provider": config.provider, "model": config.model if config.provider != "demo" else "scripted replay",
                "runner": config.runner, "max_steps": config.max_steps, "docker_tools": config.docker_tools,
                "version": __version__, "draining": manager.draining, "active_run": manager.active_id if manager.active and not manager.active.done() else None}

    @app.get("/api/model/health", dependencies=auth)
    async def model_health():
        if config.provider == "demo":
            return {"available": True, "mode": "scripted demo; no model endpoint contacted"}
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.get(config.base_url.rstrip("/") + "/models",
                    headers={"Authorization": f"Bearer {config.llm_api_key}"})
                response.raise_for_status()
                names = [m["id"] for m in response.json().get("data", [])]
            return {"available": config.model in names, "configured_model": config.model,
                    "endpoint_models": names[:30], "checks": "model listing only, not tool-call correctness"}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"available": False, "error": "Model endpoint is unavailable or has an incompatible /models response"}

    @app.get("/api/repos", dependencies=auth)
    async def repos():
        return {"repositories": manager.repositories()}

    @app.post("/api/runs", status_code=202, dependencies=auth)
    async def start_run(body: RunInput):
        try:
            return {"id": manager.create(body.repo, body.task, body.mode)}
        except DrainingError as exc:
            raise HTTPException(503, str(exc)) from None
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from None
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/runs", dependencies=auth)
    async def recent_runs():
        return {"runs": manager.store.recent()}

    @app.get("/api/runs/{run_id}", dependencies=auth)
    async def run_detail(run_id: str):
        return get_run(run_id)

    @app.post("/api/runs/{run_id}/cancel", dependencies=auth)
    async def cancel_run(run_id: str):
        get_run(run_id)
        try:
            await manager.cancel(run_id)
            return {"status": "cancelled"}
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/runs/{run_id}/approvals/{approval_id}", dependencies=auth)
    async def approve(run_id: str, approval_id: str, decision: Decision):
        get_run(run_id)
        try:
            manager.decide(run_id, approval_id, decision.approved)
            return {"accepted": True}
        except KeyError:
            raise HTTPException(409, "Approval is stale, already answered, or belongs to another run") from None

    @app.get("/api/runs/{run_id}/events", dependencies=auth)
    async def events(run_id: str, request: Request, after: int = Query(default=0, ge=0)):
        get_run(run_id)
        async def stream():
            cursor = after
            while not await request.is_disconnected():
                for event in manager.store.events(run_id, cursor):
                    cursor = event["seq"]
                    yield f"id: {cursor}\nevent: trace\ndata: {json.dumps(event)}\n\n"
                state = manager.store.get(run_id)["status"]
                if state in TERMINAL_STATES and not manager.store.events(run_id, cursor):
                    yield "event: done\ndata: {}\n\n"
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.4)
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs/{run_id}/artifacts/{kind}", dependencies=auth)
    async def artifact(run_id: str, kind: str):
        run = get_run(run_id)
        if run["status"] not in TERMINAL_STATES:
            raise HTTPException(409, "Artifacts are finalized when the run finishes")
        mapping = {"patch": "changes.patch", "report": "report.md", "trace": "trace.json"}
        if kind not in mapping:
            raise HTTPException(404, "Unknown artifact")
        path = config.data_dir / "runs" / run_id / mapping[kind]
        if not path.is_file():
            raise HTTPException(404, "Artifact not available for this run")
        return FileResponse(path, filename=f"devpilot-{run_id[:8]}-{mapping[kind]}", media_type="application/octet-stream")

    return app
