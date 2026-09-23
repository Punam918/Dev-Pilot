"""Optional official MCP SDK v2 interoperability smoke test.

This test is skipped when the SDK is unavailable. It is not a conformance suite.
"""
import os
import sys
from pathlib import Path
import pytest

mcp = pytest.importorskip("mcp", reason="Install .[interop] for the optional official SDK smoke test")
pytestmark = pytest.mark.interop


async def test_official_sdk_reads_our_stdio_server(workspace):
    from mcp import Client, StdioServerParameters
    params = StdioServerParameters(command=sys.executable, args=["-m", "devpilot.mcp.server", "files"],
             env={"DP_MCP_ROOT": str(workspace.root), "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
    async with Client(params) as client:
        listed = await client.list_tools()
        assert any(tool.name == "read_file" for tool in listed.tools)
        result = await client.call_tool("read_file", {"path": "app.py"})
        assert result.structured_content["path"] == "app.py"
