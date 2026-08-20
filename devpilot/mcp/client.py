"""Async MCP subprocess client and fixed-server tool gateway."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from . import PROTOCOL_VERSION
from ..process import clean_env
from ..safety import canonical, SafetyError, Capabilities, Workspace, redact


class MCPError(RuntimeError):
    pass


class StdioClient:
    def __init__(self, server: str, root: Path, secret: str, options: dict):
        self.server, self.root, self.secret, self.options = server, root, secret, options
        self.process = None
        self.counter = 0
        self.lock = asyncio.Lock()
        self.stderr_task = None
        self.stderr_tail = ""

    async def start(self):
        env = clean_env()
        env.update({"PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                    "DP_MCP_ROOT": str(self.root), "DP_MCP_SECRET": self.secret,
                    "DP_MCP_OPTIONS": canonical(self.options)})
        self.process = await asyncio.create_subprocess_exec(sys.executable, "-m", "devpilot.mcp.server", self.server,
                              stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                              stderr=asyncio.subprocess.PIPE, env=env,
                              limit=512_000, start_new_session=True)
        self.stderr_task = asyncio.create_task(self._drain_stderr())
        result = await self.request("initialize", {"protocolVersion": PROTOCOL_VERSION,
                                    "capabilities": {}, "clientInfo": {"name": "devpilot", "version": "0.3.0"}})
        if result.get("protocolVersion") != PROTOCOL_VERSION:
            raise MCPError("Server negotiated an unsupported protocol version")
        await self.notify("notifications/initialized")
        return self

    async def _drain_stderr(self):
        assert self.process and self.process.stderr
        while block := await self.process.stderr.read(4096):
            self.stderr_tail = (self.stderr_tail + redact(block.decode("utf-8", "replace")))[-4000:]

    async def notify(self, method: str, params: dict | None = None):
        assert self.process and self.process.stdin
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write((canonical(message) + "\n").encode())
        await self.process.stdin.drain()

    async def request(self, method: str, params: dict | None = None, timeout: int = 30) -> dict:
        async with self.lock:
            assert self.process and self.process.stdin and self.process.stdout
            self.counter += 1
            identifier = self.counter
            raw = canonical({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params or {}})
            if len(raw.encode()) > 500_000:
                raise MCPError("MCP request exceeds the message budget")
            self.process.stdin.write((raw + "\n").encode())
            await self.process.stdin.drain()
            async with asyncio.timeout(timeout):
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        raise MCPError(f"{self.server} MCP process exited: {self.stderr_tail[-500:]}")
                    response = json.loads(line)
                    if "id" not in response:
                        continue
                    if response.get("jsonrpc") != "2.0" or response["id"] != identifier:
                        raise MCPError("Mismatched MCP response")
                    if "error" in response:
                        raise MCPError(response["error"].get("message", "MCP request failed"))
                    return response["result"]

    async def close(self):
        if self.process:
            if self.process.stdin:
                self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2)
            except asyncio.TimeoutError:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await self.process.wait()
        if self.process:
            # The parent may have exited while a descendant kept a pipe open.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.stderr_task:
            try:
                await asyncio.wait_for(self.stderr_task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.stderr_task.cancel()


class Gateway:
    def __init__(self, root: Path, secret: str, options: dict):
        self.root, self.secret, self.options = root, secret, options
        self.clients: dict[str, StdioClient] = {}
        self.tools: dict[str, dict] = {}
        self.signer = Capabilities(secret)

    async def __aenter__(self):
        names = ["files", "git", "docs", "terminal", "database"]
        if self.options.get("docker_tools"):
            names.append("docker")
        try:
            for name in names:
                client = StdioClient(name, self.root, self.secret, self.options)
                self.clients[name] = client
                await client.start()
                result = await client.request("tools/list")
                for tool in result["tools"]:
                    key = f"{name}__{tool['name']}"
                    self.tools[key] = tool
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *args):
        await asyncio.gather(*(client.close() for client in self.clients.values()), return_exceptions=True)

    def model_tools(self) -> list[dict]:
        return [{"type": "function", "function": {"name": name, "description": tool["description"],
                                                  "parameters": tool["inputSchema"]}}
                for name, tool in self.tools.items()]

    def validate(self, name: str, args: dict) -> str:
        if name not in self.tools:
            raise SafetyError("Unknown or disabled tool")
        errors = list(Draft202012Validator(self.tools[name]["inputSchema"]).iter_errors(args))
        if errors:
            raise SafetyError("Invalid arguments: " + errors[0].message[:400])
        return self.tools[name]["_meta"]["devpilot/risk"]

    async def call(self, name: str, args: dict, capability: str | None = None) -> dict:
        self.validate(name, args)
        server, tool = name.split("__", 1)
        params = {"name": tool, "arguments": args}
        if capability:
            params["_meta"] = {"devpilot/approval": capability}
        result = await self.clients[server].request("tools/call", params,
                          timeout=int(self.options.get("tool_timeout", 90)) + 20)
        value = result.get("structuredContent")
        if value is None:
            value = json.loads(result["content"][0]["text"])
        return {"ok": not result.get("isError", False), "result": value}
