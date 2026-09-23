#!/usr/bin/env python3
"""Harmless live endpoint/tool-call smoke test; does not execute repository code."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devpilot.config import Settings
from devpilot.models import OpenAIModel


async def check() -> int:
    settings = Settings()
    if settings.provider != "openai":
        print("Set DP_PROVIDER=openai and configure a real local model first. Demo is not inference.")
        return 2
    model = OpenAIModel(settings)
    tools = [{"type": "function", "function": {
        "name": "add", "description": "Add two integers. Always use this tool for the requested calculation.",
        "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                       "required": ["a", "b"], "additionalProperties": False}}}]
    try:
        listing = await model.client.get(settings.base_url.rstrip("/") + "/models",
                         headers={"Authorization": "Bearer " + settings.llm_api_key})
        listing.raise_for_status()
        names = [row["id"] for row in listing.json().get("data", [])]
        print("Configured model listed:", settings.model in names)
        reply = await model.complete([
            {"role": "system", "content": "Use the add tool. Do not calculate in text. /no_think"},
            {"role": "user", "content": "Call add with a=2 and b=3."}], tools)
        valid = bool(reply.calls and reply.calls[0].name == "add" and
                     json.loads(reply.calls[0].arguments) == {"a": 2, "b": 3})
        print(json.dumps({"model": settings.model, "structured_tool_call_valid": valid,
                          "tool_count": len(reply.calls), "usage": reply.usage,
                          "note": "No returned tool was executed. This is not a debugging benchmark."}, indent=2))
        return 0 if valid else 1
    except Exception as exc:
        # Do not print raw HTTP bodies/headers or API credentials.
        print(f"Model smoke test failed ({type(exc).__name__}). Check the endpoint, model, and tool parser.")
        return 1
    finally:
        await model.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
