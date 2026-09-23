"""Agent state machine, approvals, durable events, and evidence-based artifacts."""
from __future__ import annotations

import asyncio
import json
import platform
import re
import secrets
import time
import uuid
from pathlib import Path

from . import __version__, gitops
from .config import Settings
from .demo import validate_demo
from .mcp.client import Gateway
from .models import DemoModel, OpenAIModel
from .prompts import SYSTEM_PROMPT
from .safety import Workspace, SafetyError, copy_workspace, canonical, digest, redact_tree, redact
from .store import Store
from .telemetry import Telemetry

TERMINAL_STATES = {"completed", "failed", "cancelled", "interrupted", "limit_reached"}


class BusyError(RuntimeError):
    pass


class DrainingError(BusyError):
    pass


class RunManager:
    def __init__(self, settings: Settings, *, recover: bool = True):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings.data_dir.chmod(0o700)
        settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.store = Store(settings.data_dir / "audit.sqlite3")
        if recover:
            self.store.interrupt_unfinished()
        self.draining = False
        self.telemetry = Telemetry(settings)
        self.active: asyncio.Task | None = None
        self.active_id: str | None = None
        self.approvals: dict[str, tuple[str, asyncio.Future]] = {}

    def repository(self, name: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name):
            raise SafetyError("Select a repository name, not a path or URL")
        path = self.settings.workspace_dir / name
        Workspace(path)
        return path

    def repositories(self) -> list[str]:
        return sorted(p.name for p in self.settings.workspace_dir.iterdir()
                      if p.is_dir() and not p.is_symlink()
                      and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", p.name))

    def create(self, repo: str, task: str, mode: str = "repair") -> str:
        if self.draining:
            raise DrainingError("Deployment maintenance in progress; new runs are paused")
        if self.active and not self.active.done():
            raise BusyError("One run at a time is supported; finish or cancel the current run")
        if self.store.count() >= self.settings.max_runs:
            raise BusyError("Run retention limit reached. Archive the data directory while DevPilot is stopped")
        source = self.repository(repo)
        if mode not in {"diagnose", "repair"} or not 1 <= len(task.strip()) <= 4000:
            raise ValueError("Invalid mode or task length")
        case_id = validate_demo(repo, source) if self.settings.provider == "demo" else None
        identifier = uuid.uuid4().hex
        self.store.create(identifier, {"repo": repo, "task": redact(task), "mode": mode,
            "provider": self.settings.provider,
            "model": "scripted-fixture-policy (NOT an LLM)" if case_id else self.settings.model,
            "runner": self.settings.runner, "pending_approval": None, "final": "",
            "verification": {"verified": False, "tests_executed": False}, "metrics": {}})
        self.active_id = identifier
        self.active = asyncio.create_task(self._execute(identifier, source, case_id), name=f"run-{identifier}")
        return identifier

    def emit(self, run_id: str, kind: str, data: dict):
        self.store.event(run_id, kind, redact_tree(data))
        self.telemetry.event(kind, data)

    def decide(self, run_id: str, approval_id: str, allow: bool) -> None:
        item = self.approvals.get(approval_id)
        if item is None or item[0] != run_id or item[1].done():
            raise KeyError("Approval is missing, expired, or already answered")
        self.emit(run_id, "approval_decision", {"approval_id": approval_id, "approved": allow})
        item[1].set_result(allow)

    async def cancel(self, run_id: str):
        self.store.get(run_id)
        if self.active_id != run_id or not self.active or self.active.done():
            raise BusyError("Run is not active")
        self.active.cancel()
        await asyncio.gather(self.active, return_exceptions=True)
        # A task cancelled before its first execution cannot run its finally block.
        if self.store.get(run_id)["status"] not in TERMINAL_STATES:
            self.store.update(run_id, status="cancelled", pending_approval=None,
                              final="Cancelled before execution started.")
            self.emit(run_id, "run_finished", {"status": "cancelled"})

    def drain(self):
        self.draining = True
        self.telemetry.accepting.set(0)

    def resume(self):
        self.draining = False
        self.telemetry.accepting.set(1)

    async def shutdown(self):
        self.drain()
        if self.active and not self.active.done() and self.active_id:
            await self.cancel(self.active_id)

    async def _approval(self, run_id: str, name: str, args: dict, risk: str, workspace: Workspace) -> str | None:
        approval_id = uuid.uuid4().hex
        snapshot = workspace.fingerprint()
        preview = ""
        if name == "files__replace_text":
            _, preview = workspace.edit_preview(**args)
        future = asyncio.get_running_loop().create_future()
        self.approvals[approval_id] = (run_id, future)
        details = {"id": approval_id, "tool": name, "risk": risk, "arguments": redact_tree(args),
                   "arguments_sha256": digest(canonical(args)), "snapshot_sha256": snapshot,
                   "preview_diff": redact(preview), "expires_in_seconds": self.settings.approval_timeout,
                   "warning": ("Tests execute code. Docker isolation is recommended." if risk == "execute"
                               else "Only the disposable workspace will be edited. Review the exact diff.")}
        self.store.update(run_id, status="awaiting_approval", pending_approval=details)
        self.emit(run_id, "approval_required", details)
        try:
            allowed = await asyncio.wait_for(future, timeout=self.settings.approval_timeout)
            return snapshot if allowed else None
        except asyncio.TimeoutError:
            self.emit(run_id, "approval_expired", {"approval_id": approval_id})
            return None
        finally:
            self.approvals.pop(approval_id, None)
            self.store.update(run_id, status="running", pending_approval=None)

    async def _execute(self, run_id: str, source: Path, case_id: str | None):
        started = time.monotonic()
        run_dir = self.settings.data_dir / "runs" / run_id
        root = run_dir / "workspace"
        model = None
        status, final = "failed", "Run did not complete."
        last_test = None
        initial_source = ""
        metrics = {"model_turns": 0, "tool_calls": 0, "tool_errors": 0,
                   "llm_ms": 0, "tool_ms": 0, "prompt_tokens": None, "completion_tokens": None}
        try:
            async with asyncio.timeout(self.settings.run_timeout):
                self.store.update(run_id, status="running")
                self.emit(run_id, "run_started", {"provider": self.settings.provider, "version": __version__,
                    "note": "Scripted integration replay, not model intelligence" if case_id else "Live configured model; quality is not guaranteed"})
                initial_source = Workspace(source).fingerprint()
                summary = await asyncio.to_thread(copy_workspace, source, root)
                await asyncio.to_thread(gitops.initialize, root)
                workspace = Workspace(root)
                self.emit(run_id, "snapshot_created", {**summary, "input_sha256": workspace.fingerprint()})
                model = DemoModel(case_id) if case_id else OpenAIModel(self.settings)
                options = {"runner": self.settings.runner, "trust_local_code": self.settings.trust_local_code,
                           "tool_timeout": self.settings.tool_timeout, "runner_image": self.settings.runner_image,
                           "docker_tools": self.settings.docker_tools, "docker_label": self.settings.docker_label,
                           **{key: str(getattr(self.settings, key)) for key in ("kube_api_url", "kube_namespace", "kube_token_file", "kube_ca_file", "kube_runtime_class", "kube_image_pull_secret")},
                           "kube_job_timeout": self.settings.kube_job_timeout}
                run = self.store.get(run_id)
                messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\nApplication mode: {run['mode']}."},
                            {"role": "user", "content": run["task"]}]
                secret = secrets.token_hex(32)
                async with Gateway(root, secret, options) as gateway:
                    self.emit(run_id, "mcp_connected", {"servers": list(gateway.clients),
                              "tool_count": len(gateway.tools), "protocol": "2025-06-18 stdio subset"})
                    tools = gateway.model_tools()
                    if run["mode"] == "diagnose":
                        tools = [t for t in tools if gateway.tools[t["function"]["name"]]["_meta"]["devpilot/risk"] != "write"]
                    for turn in range(self.settings.max_steps):
                        if len(canonical(messages)) > self.settings.max_context_chars:
                            status, final = "limit_reached", "Context budget reached; inspect the trace and narrow the task."
                            break
                        self.emit(run_id, "model_request", {"turn": turn + 1})
                        tick = time.monotonic()
                        with self.telemetry.span("model.complete", provider=self.settings.provider):
                            reply = await model.complete(messages, tools)
                        model_ms = round((time.monotonic() - tick) * 1000)
                        self.emit(run_id, "model_result", {"duration_ms": model_ms, "usage": reply.usage})
                        metrics["llm_ms"] += model_ms
                        metrics["model_turns"] += 1
                        for key in ("prompt_tokens", "completion_tokens"):
                            value = reply.usage.get(key)
                            if isinstance(value, int) and value >= 0:
                                metrics[key] = (metrics[key] or 0) + value
                        messages.append(reply.message())
                        if not reply.calls:
                            final = reply.content or "Model returned no final explanation. Inspect the recorded evidence."
                            status = "completed"
                            break
                        if reply.content:
                            self.emit(run_id, "assistant_note", {"text": reply.content[:6000]})
                        for call in reply.calls:
                            if metrics["tool_calls"] >= self.settings.max_tool_calls:
                                raise SafetyError("Tool-call budget reached")
                            metrics["tool_calls"] += 1
                            result = {"ok": False, "result": {"error": "Tool was not executed"}}
                            try:
                                args = json.loads(call.arguments)
                                risk = gateway.validate(call.name, args)
                                self.emit(run_id, "tool_requested", {"call_id": call.id, "tool": call.name, "arguments": args})
                                if run["mode"] == "diagnose" and risk == "write":
                                    raise SafetyError("Diagnose mode does not permit edits")
                                capability = None
                                if risk != "read":
                                    snapshot = await self._approval(run_id, call.name, args, risk, workspace)
                                    if snapshot is None:
                                        raise SafetyError("Action denied or approval expired; do not bypass this decision")
                                    capability = gateway.signer.issue(call.name, args, snapshot)
                                tick = time.monotonic()
                                with self.telemetry.span("mcp.tool", tool=call.name):
                                    result = await gateway.call(call.name, args, capability)
                                duration = round((time.monotonic() - tick) * 1000)
                                metrics["tool_ms"] += duration
                                result["duration_ms"] = duration
                                if call.name == "terminal__run_tests" and result["ok"]:
                                    last_test = result["result"]
                            except (ValueError, SafetyError) as exc:
                                result = {"ok": False, "result": {"error": redact(str(exc))[:1200]}}
                            if not result["ok"]:
                                metrics["tool_errors"] += 1
                            self.emit(run_id, "tool_result", {"call_id": call.id, "tool": call.name, **result})
                            messages.append({"role": "tool", "tool_call_id": call.id, "content": canonical(redact_tree(result))})
                        self.store.update(run_id, metrics=metrics)
                    else:
                        status, final = "limit_reached", "Model-turn budget reached. No unobserved success is claimed."
        except asyncio.CancelledError:
            status, final = "cancelled", "Run cancelled. Review any already-approved changes in the exported patch."
        except TimeoutError:
            status, final = "limit_reached", "Run time budget reached. The trace records completed actions only."
        except Exception as exc:
            status, final = "failed", f"{type(exc).__name__}: {redact(str(exc))[:1500]}"
            self.emit(run_id, "error", {"message": final})
        finally:
            if model is not None:
                await model.close()
            metrics["wall_ms"] = round((time.monotonic() - started) * 1000)
            verification = {"verified": False, "tests_executed": last_test is not None,
                            "last_exit_code": None if last_test is None else last_test.get("exit_code"),
                            "snapshot_matches_tested": False, "source_unchanged": None}
            patch = ""
            try:
                if root.is_dir():
                    current = Workspace(root).fingerprint()
                    verification["snapshot_sha256"] = current
                    if last_test:
                        matches = current == last_test.get("snapshot_sha256") and last_test.get("snapshot_unchanged", False)
                        verification["snapshot_matches_tested"] = bool(matches)
                        verification["verified"] = bool(matches and last_test.get("exit_code") == 0
                            and not last_test.get("timed_out") and not last_test.get("output_limited"))
                    if (root / ".git").exists():
                        patch = await asyncio.to_thread(gitops.diff, root)
                verification["source_unchanged"] = initial_source == Workspace(source).fingerprint() if initial_source else None
            except Exception as exc:
                self.emit(run_id, "artifact_warning", {"message": redact(str(exc))})
            self.store.update(run_id, status=status, final=redact(final), metrics=metrics,
                              verification=verification, pending_approval=None, patch_available=bool(patch))
            self.emit(run_id, "run_finished", {"status": status, "verification": verification, "metrics": metrics})
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "changes.patch").write_text(patch, encoding="utf-8")
            self._export(run_id, run_dir)

    def _export(self, run_id: str, run_dir: Path):
        run = self.store.get(run_id)
        trace = self.store.events(run_id)
        payload = {"schema_version": 1, "project_version": __version__, "python": platform.python_version(),
                   "run": run, "events": trace,
                   "disclaimer": "Demo provider is scripted. Verification means the fixed test command exited zero on the unchanged final snapshot, not proof of general correctness."}
        (run_dir / "trace.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        check = run["verification"]
        lines = ["# DevPilot run report", "", f"- Run: `{run_id}`", f"- Repository: `{run['repo']}`",
                 f"- Mode: `{run['mode']}`", f"- Provider: `{run['provider']}`", f"- Model: `{run['model']}`",
                 f"- Status: `{run['status']}`", f"- Runner: `{run['runner']}`", "",
                 "## Independently recorded validation", "", "```json", json.dumps(check, indent=2), "```", "",
                 "A passing check is not proof of semantic correctness or production readiness.", "",
                 "## Assistant explanation", "", run["final"], "", "## Metrics", "", "```json",
                 json.dumps(run["metrics"], indent=2), "```", "", "## Tool evidence", ""]
        for event in trace:
            if event["kind"] == "tool_result":
                data = event["data"]
                lines += [f"### {data['tool']}", "", "```json", json.dumps(data["result"], indent=2, ensure_ascii=False), "```", ""]
        lines += ["## Scope and limitations", "",
                  "This artifact is local development evidence. Repository data may still contain secrets; review before publishing.",
                  "Demo/replay runs do not measure a language model. Real-model quality, Docker isolation, and GPU performance require separate validation.", ""]
        (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
