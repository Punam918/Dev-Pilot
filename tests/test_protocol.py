import json
import pytest
from devpilot.mcp.server import MCPServer
from devpilot.mcp.client import StdioClient, Gateway
from devpilot.mcp import PROTOCOL_VERSION
from devpilot.safety import Capabilities, digest, SafetyError
from devpilot.gitops import initialize


def initialized(server):
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTOCOL_VERSION}})
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return server


def request(server, method, params=None):
    return server.handle({"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}})


def test_lifecycle_requires_initialization(workspace):
    server = MCPServer("files", workspace.root, "s" * 64)
    assert request(server, "tools/list")["error"]["code"] == -32002
    initialized(server)
    assert request(server, "tools/list")["result"]["tools"]
    assert request(server, "ping")["result"] == {}


@pytest.mark.parametrize("bad", [[], {}, {"jsonrpc": "1.0", "method": "ping", "id": 1}, {"jsonrpc": "2.0", "method": "ping", "id": None}])
def test_invalid_jsonrpc_is_rejected(workspace, bad):
    server = MCPServer("files", workspace.root, "s" * 64)
    assert server.handle(bad)["error"]["code"] == -32600


def test_unknown_method_and_invalid_arguments(workspace):
    server = initialized(MCPServer("files", workspace.root, "s" * 64))
    assert request(server, "not/a/method")["error"]["code"] == -32601
    result = request(server, "tools/call", {"name": "read_file", "arguments": {"path": "app.py", "shell": "anything"}})
    assert result["error"]["code"] == -32602


def test_tools_resources_and_prompts(workspace):
    server = initialized(MCPServer("files", workspace.root, "s" * 64))
    assert request(server, "resources/list")["result"]["resources"][0]["uri"] == "workspace://overview"
    text = request(server, "resources/read", {"uri": "repo:///app.py"})["result"]["contents"][0]["text"]
    assert text == "value = 1\n"
    assert "messages" in request(server, "prompts/get", {"name": "debug_repository", "arguments": {"task": "fix bug"}})["result"]
    assert "error" in request(server, "resources/read", {"uri": "repo:///../secret"})


def test_server_checks_approval_independently(workspace):
    server = initialized(MCPServer("files", workspace.root, "s" * 64))
    args = {"path": "app.py", "old": "value = 1", "new": "value = 2", "expected_sha256": digest("value = 1\n")}
    denied = request(server, "tools/call", {"name": "replace_text", "arguments": args})["result"]
    assert denied["isError"]
    assert workspace.read("app.py") == "value = 1\n"
    token = Capabilities("s" * 64).issue("files__replace_text", args, workspace.fingerprint())
    allowed = request(server, "tools/call", {"name": "replace_text", "arguments": args, "_meta": {"devpilot/approval": token}})["result"]
    assert not allowed["isError"]
    assert workspace.read("app.py") == "value = 2\n"


async def test_real_subprocess_stdio(workspace):
    client = StdioClient("files", workspace.root, "x" * 64, {})
    try:
        await client.start()
        tools = await client.request("tools/list")
        assert {t["name"] for t in tools["tools"]} == {"list_files", "read_file", "replace_text"}
        result = await client.request("tools/call", {"name": "read_file", "arguments": {"path": "app.py"}})
        assert result["structuredContent"]["sha256"] == digest("value = 1\n")
        assert await client.request("ping") == {}
    finally:
        await client.close()
    assert client.process.returncode == 0


async def test_gateway_aggregates_namespaces_and_blocks_unknown(workspace):
    initialize(workspace.root)
    async with Gateway(workspace.root, "x" * 64, {}) as gateway:
        assert len(gateway.clients) == 5
        assert "docs__search" in gateway.tools
        assert "docker__logs" not in gateway.tools
        assert (await gateway.call("files__list_files", {}))["ok"]
        with pytest.raises(SafetyError):
            await gateway.call("terminal__shell", {"command": "anything"})
