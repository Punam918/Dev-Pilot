"""OpenAI-compatible local inference plus a clearly separated scripted replay."""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Settings
from .demo import CASES
from .safety import canonical


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str

    def wire(self):
        return {"id": self.id, "type": "function", "function": {"name": self.name, "arguments": self.arguments}}


@dataclass
class Reply:
    content: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int | None] = field(default_factory=dict)

    def message(self) -> dict:
        result = {"role": "assistant", "content": self.content or None}
        if self.calls:
            result["tool_calls"] = [call.wire() for call in self.calls]
        return result


class ModelError(RuntimeError):
    pass


class OpenAIModel:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout, trust_env=False, transport=transport)

    async def complete(self, messages: list[dict], tools: list[dict]) -> Reply:
        body = {"model": self.settings.model, "messages": messages, "tools": tools,
                "tool_choice": "auto", "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_output_tokens, "stream": False}
        response = None
        for attempt in range(3):
            try:
                response = await self.client.post(self.settings.base_url.rstrip("/") + "/chat/completions",
                           headers={"Authorization": f"Bearer {self.settings.llm_api_key}"}, json=body)
                if response.status_code in {429, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                response.raise_for_status()
                break
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                raise ModelError("Cannot reach the inference endpoint. Check Ollama/vLLM, model name, port, and timeout") from exc
            except httpx.HTTPStatusError as exc:
                raise ModelError(f"Inference returned HTTP {exc.response.status_code}; verify the endpoint, model, API key, and tool-call parser") from exc
        try:
            assert response is not None
            if len(response.content) > 400_000:
                raise ModelError("Inference response exceeded the size budget")
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelError("Model output was truncated. Increase DP_MAX_OUTPUT_TOKENS or disable model thinking")
            message = choice["message"]
            content = message.get("content") or ""
            if not isinstance(content, str):
                raise ModelError("Only text chat completions are supported")
            # Do not surface provider-specific reasoning fields or think blocks.
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            calls = []
            for item in message.get("tool_calls") or []:
                fn = item["function"]
                args = fn.get("arguments", "{}")
                if not isinstance(args, str):
                    args = canonical(args)
                if len(args) > 65000 or len(fn["name"]) > 100:
                    raise ModelError("Model tool call exceeded the size budget")
                calls.append(ToolCall(item.get("id") or "call_" + uuid.uuid4().hex, fn["name"], args))
            if len(calls) > 8 or len({c.id for c in calls}) != len(calls):
                raise ModelError("Too many tool calls or duplicate tool-call IDs")
            usage = data.get("usage") or {}
            return Reply(content, calls, {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")})
        except ModelError:
            raise
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelError("Malformed OpenAI-compatible response; no tool was executed") from exc

    async def close(self):
        await self.client.aclose()


class DemoModel:
    """Fixed action sequence for integration checks. Not an LLM benchmark."""
    def __init__(self, case_id: str):
        self.case = CASES[case_id]
        self.step = 0

    async def complete(self, messages: list[dict], tools: list[dict]) -> Reply:
        self.step += 1
        results = [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]
        if results and not results[-1].get("ok", False):
            return Reply("SCRIPTED DEMO: stopped after a denied or failed tool operation. Inspect the trace; no successful verification is claimed.")
        c = self.case
        plan = {1: ("files__list_files", {}),
                2: ("docs__search", {"query": c["query"], "limit": 3}),
                3: ("files__read_file", {"path": c["path"]}),
                4: ("terminal__run_tests", {}),
                6: ("terminal__run_tests", {}),
                7: ("git__diff", {})}
        if self.step == 5:
            if not any(t["function"]["name"] == "files__replace_text" for t in tools):
                return Reply(f"SCRIPTED DEMO: the baseline tests expose the intentionally seeded bug in {c['path']}. Diagnose mode does not permit edits. No fix was applied.")
            file_result = next(r["result"] for r in results if r.get("result", {}).get("path") == c["path"] and "sha256" in r["result"])
            plan[5] = ("files__replace_text", {"path": c["path"], "old": c["old"], "new": c["new"],
                                             "expected_sha256": file_result["sha256"]})
        if self.step in plan:
            name, args = plan[self.step]
            return Reply("", [ToolCall(f"demo_{self.step}", name, canonical(args))])
        executions = [r["result"] for r in results if "exit_code" in r.get("result", {}) and "runner" in r["result"]]
        if len(executions) >= 2:
            before, after = executions[0], executions[-1]
            return Reply(f"SCRIPTED DEMO - no language model was called.\n\n"
                         f"Evidence: {c['path']} and the captured pytest output.\n"
                         f"Applied the fixture's predefined one-line repair after approval.\n"
                         f"Baseline pytest exit code: {before['exit_code']}.\n"
                         f"Post-patch pytest exit code: {after['exit_code']}.\n"
                         "The original repository was not changed. Download and review the patch.\n"
                         "These results validate the integration workflow, not autonomous model quality.")
        return Reply("SCRIPTED DEMO ended without complete before/after test evidence.")

    async def close(self):
        return None
