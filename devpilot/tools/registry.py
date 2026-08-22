"""Explicit tool catalog shared by MCP servers and their enforcement layer."""
from dataclasses import dataclass
from typing import Callable, Any

from .. import gitops
from ..retrieval import search
from ..safety import Workspace, digest, redact
from .runner import run_tests
from .database import query as database_query
from . import docker


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    handler: Callable[..., Any]
    risk: str = "read"

    def wire(self) -> dict:
        return {"name": self.name, "description": self.description, "inputSchema": self.schema,
                "annotations": {"readOnlyHint": self.risk == "read",
                                "destructiveHint": self.risk != "read",
                                "openWorldHint": False},
                "_meta": {"devpilot/risk": self.risk}}


def obj(properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties or {}, "required": required or [],
            "additionalProperties": False}


def string(maximum: int = 1000, minimum: int = 1) -> dict:
    return {"type": "string", "minLength": minimum, "maxLength": maximum}


def integer(default: int, minimum: int, maximum: int) -> dict:
    return {"type": "integer", "default": default, "minimum": minimum, "maximum": maximum}


def registry(server: str, workspace: Workspace, options: dict) -> dict[str, Tool]:
    path_schema = string(300)
    tools: list[Tool]
    if server == "files":
        def read_file(path: str, start_line: int = 1, end_line: int = 200):
            text = workspace.read(path)
            lines = text.splitlines()
            if end_line < start_line or end_line - start_line > 200:
                raise ValueError("Read an ordered range of at most 201 lines")
            selected = lines[start_line - 1:end_line]
            return {"path": path, "sha256": digest(text), "total_lines": len(lines),
                    "start_line": start_line, "end_line": min(end_line, len(lines)),
                    "content": redact("\n".join(selected))[:24000],
                    "numbered": redact("\n".join(f"{i}: {line}" for i, line in enumerate(selected, start_line)))[:24000]}
        tools = [
            Tool("list_files", "List non-secret regular files in this disposable workspace.", obj(),
                 lambda: {"files": workspace.files()}),
            Tool("read_file", "Read UTF-8 source with line numbers and a SHA256 hash required for edits.",
                 obj({"path": path_schema, "start_line": integer(1, 1, 100000), "end_line": integer(200, 1, 100000)}, ["path"]), read_file),
            Tool("replace_text", "Request approval to replace one exact text occurrence in application code. Never edit tests. Requires the current file SHA256.",
                 obj({"path": path_schema, "old": string(30000), "new": string(30000, 0),
                      "expected_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"}},
                     ["path", "old", "new", "expected_sha256"]), workspace.replace, "write")]
    elif server == "git":
        tools = [Tool("status", "Read Git status of the disposable snapshot, not the original repository.", obj(),
                      lambda: gitops.git(workspace.root, ["status", "--short"])),
                 Tool("diff", "Return the complete text patch relative to the immutable input snapshot.", obj(),
                      lambda: {"diff": gitops.diff(workspace.root)}),
                 Tool("history", "Read this snapshot's baseline commit. Source repository history is not imported.", obj(),
                      lambda: gitops.git(workspace.root, ["log", "-5", "--format=%h %s"]))]
    elif server == "docs":
        tools = [Tool("search", "BM25 search across code and documentation. Returns source paths and line ranges. Reindexes the current snapshot; no embedding model is used.",
                      obj({"query": string(500), "limit": integer(5, 1, 10)}, ["query"]),
                      lambda query, limit=5: search(workspace, query, limit))]
    elif server == "terminal":
        tools = [Tool("run_tests", "Request human approval to run the fixed Python pytest suite. Tests execute arbitrary code; use Docker for non-demo repositories.",
                      obj(), lambda: run_tests(workspace, options), "execute")]
    elif server == "database":
        tools = [
            Tool("schema", "Inspect tables in a small SQLite database copied into this workspace.",
                 obj({"path": path_schema}, ["path"]),
                 lambda path: database_query(workspace, path, "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")),
            Tool("query", "Execute a bounded SELECT on a workspace SQLite database with a read-only connection and SQLite authorizer. No PostgreSQL connection is implemented.",
                 obj({"path": path_schema, "sql": string(4000), "limit": integer(50, 1, 100)}, ["path", "sql"]),
                 lambda path, sql, limit=50: database_query(workspace, path, sql, limit))]
    elif server == "docker":
        tools = [
            Tool("list_containers", "List only operator-label-scoped Docker containers. Read-only and explicitly opt-in.", obj(),
                 lambda: docker.list_containers(workspace.root, options)),
            Tool("inspect", "Inspect a label-scoped container's state without exposing environment variables.",
                 obj({"container_id": string(64, 12)}, ["container_id"]),
                 lambda container_id: docker.inspect_container(workspace.root, options, container_id)),
            Tool("logs", "Read the last 100 log lines from a label-scoped container. Redaction is best effort.",
                 obj({"container_id": string(64, 12)}, ["container_id"]),
                 lambda container_id: docker.logs(workspace.root, options, container_id))]
    else:
        raise ValueError(f"Unknown built-in MCP server: {server}")
    return {tool.name: tool for tool in tools}
