# MCP implementation and compatibility boundary

## What this release speaks

DevPilot includes an independently implemented, minimal **Model Context Protocol 2025-06-18** subset over stdio. It uses newline-delimited JSON-RPC 2.0, initializes a session before exposing tools, and keeps operational output off protocol stdout.

Implemented methods:

| Area | Methods |
|---|---|
| Lifecycle | `initialize`, `notifications/initialized`, `ping` |
| Tools | `tools/list`, `tools/call` |
| Resources | `resources/list`, `resources/templates/list`, `resources/read` |
| Prompts | `prompts/list`, `prompts/get` |

The application currently uses tool discovery and invocation; resources and prompts are available for protocol inspection/interoperability tests. Unsupported methods fail explicitly. Tool outputs include text content and structured content, with `isError` for tool failures. Read-only annotations are hints, not authorization; the DevPilot risk metadata and server checks enforce the application's rules.

## Not implemented or claimed

This is not the official Python SDK, full MCP conformance, latest-spec parity, Streamable HTTP, OAuth, a remote tool marketplace, sampling, elicitation, roots negotiation, bidirectional request orchestration, pagination at scale, protocol-level cancellation, or a certification. There is one request at a time per subprocess and a fixed small registry.

Application cancellation closes/terminates the managed subprocesses instead of relying on protocol cancellation. Do not attach arbitrary untrusted MCP server executables: the gateway's allowlist is part of the security design.

## Server processes

The gateway starts the following using the current Python interpreter:

```bash
python -m devpilot.mcp.server files
python -m devpilot.mcp.server git
python -m devpilot.mcp.server docs
python -m devpilot.mcp.server terminal
python -m devpilot.mcp.server database
```

The optional Docker observer is enabled only by the operator. Root, per-run secret, and tool settings are delivered through a cleaned subprocess environment. No standalone server should be exposed to an untrusted caller or configured with a real production workspace.

Tool names are namespaced to the model, for example `files__read_file`, `docs__search`, `terminal__run_tests`, and `database__query`. The gateway strips the namespace only when routing to the chosen server.

## Interoperability evidence

The packaged test suite exercises actual subprocess round trips, lifecycle handling, JSON-schema validation, resources/prompts, and independent approval rejection. This proves the tested DevPilot client/server behavior, not compatibility with every third-party client.

An **optional official SDK v2 smoke test** is provided:

```bash
python -m pip install -e ".[interop]"
python -m pytest tests/test_sdk_interop.py -q
```

It was skipped in the packaging environment because the SDK was unavailable and package-network access failed. Do not describe this integration as validated until you run it successfully. SDK APIs and supported protocol revisions evolve; record the installed SDK version with the result.

## Why MCP is here

The model-facing function schema is separate from the server implementation. The same underlying tool can be discovered, validated, and called through a standardized boundary instead of being hardwired into model prompts. Permissions, isolation, and model correctness remain separate concerns.

See [official references](SOURCES.md) and the [architecture](ARCHITECTURE.md).
