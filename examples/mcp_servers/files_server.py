#!/usr/bin/env python3
"""A tiny, dependency-free MCP server over stdio — read-only filesystem tools.

It speaks newline-delimited JSON-RPC 2.0 on stdin/stdout (the MCP stdio
transport): `initialize`, `tools/list`, `tools/call`. Two tools, both read-only:

  * list_dir(path=".")  — list entries under a directory
  * read_file(path)     — return a text file's contents

All access is confined to a root directory (argv[1], default: cwd); path
traversal outside the root is refused. Logs go to stderr so stdout stays pure
JSON-RPC.

This is both the test fixture for `tiles_ai.connectors.MCPConnector` and the real
backend for the `connectors/local-files` connector. Run it directly:

    python3 examples/mcp_servers/files_server.py /path/to/docs
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
MAX_BYTES = 100_000

TOOLS = [
    {
        "name": "list_dir",
        "description": "List the entries in a directory (relative to the root).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file (relative to the root).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "whoami",
        "description": "Return the FILES_USER env var (demonstrates env passthrough).",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
]


def _safe(path: str) -> Path:
    """Resolve `path` under ROOT, refusing anything that escapes it."""
    resolved = (ROOT / (path or ".")).resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"path '{path}' escapes the root")
    return resolved


def _list_dir(path: str = ".") -> str:
    target = _safe(path)
    if not target.is_dir():
        raise ValueError(f"not a directory: {path}")
    entries = sorted(
        f"{p.name}/" if p.is_dir() else p.name for p in target.iterdir()
    )
    return "\n".join(entries) if entries else "(empty)"


def _read_file(path: str) -> str:
    target = _safe(path)
    if not target.is_file():
        raise ValueError(f"not a file: {path}")
    data = target.read_bytes()[:MAX_BYTES]
    return data.decode("utf-8", "replace")


def _call_tool(name: str, args: dict) -> str:
    if name == "list_dir":
        return _list_dir(args.get("path", "."))
    if name == "read_file":
        return _read_file(args["path"])
    if name == "whoami":
        return os.environ.get("FILES_USER", "anonymous")
    raise ValueError(f"unknown tool '{name}'")


def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _handle(message: dict):
    method = message.get("method")
    req_id = message.get("id")

    if method == "initialize":
        return _result(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "files-server", "version": "0.0.1"},
            },
        )
    if method == "notifications/initialized":
        return None  # notification, no response
    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        try:
            text = _call_tool(params["name"], params.get("arguments", {}))
            return _result(req_id, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # report tool errors as MCP tool errors
            return _result(
                req_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )
    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }
    return None


def main() -> None:
    print(f"files-server: root={ROOT}", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
