"""A deliberately narrow, version-pinned MCP stdio implementation.

This is actual newline-delimited JSON-RPC over subprocess pipes, not a tool-call
mock. It supports the documented 2025-06-18 lifecycle, tools, resources, prompts,
and ping subset. It is not the official SDK or a full implementation of MCP.
"""
PROTOCOL_VERSION = "2025-06-18"
