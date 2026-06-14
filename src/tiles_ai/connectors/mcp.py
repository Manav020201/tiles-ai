"""A generic MCP-backed connector.

This is the connector the whole "connector = a binding to an app's MCP server"
thesis rests on. It speaks the Model Context Protocol (JSON-RPC 2.0 over a stdio
subprocess) using only the standard library — no SDK dependency, same spirit as
the stdlib model clients.

Design choices that keep the rest of the system unchanged:

  * The **manifest stays the authority** on the tool surface and each tool's
    `side_effect` flag. The registry validates a tile's `allowed_tools` against
    the manifest at load time (no server required), and the permission gate
    trusts the manifest's `side_effect`. The live MCP server *executes* tools;
    it does not get to redefine what's allowed or what's considered a side
    effect. (Use `live_tools()` to introspect a running server when authoring a
    manifest.)
  * It implements the same `Connector` interface as the mock, so a tile binding
    a mock connector and a tile binding a real MCP connector are byte-identical.

Transport: the connector manifest's `endpoint` is the command line that launches
the MCP server, e.g. `python3 examples/mcp_servers/files_server.py .`. It is
shell-split and run as a subprocess. (Launching a configured command is how every
MCP client works; the command lives in your own manifest.)
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from typing import Any

from ..contracts import (
    AuthConfig,
    CallContext,
    Connector,
    ConnectorManifest,
    Session,
    ToolResult,
    ToolSpec,
)

PROTOCOL_VERSION = "2024-11-05"
_READ_TIMEOUT = 30.0  # seconds to wait for a single JSON-RPC response


class MCPError(Exception):
    """An MCP transport or protocol error."""


class StdioMCPClient:
    """A minimal MCP client over a stdio subprocess (newline-delimited JSON-RPC).

    Requests are issued and awaited one at a time (a tile calls one tool at a
    time), so a simple write-then-read-until-matching-id loop is sufficient and
    avoids a full async dispatcher. Server notifications are skipped by id.
    """

    def __init__(self, command: list[str], *, cwd: str | None = None) -> None:
        self._command = command
        self._cwd = cwd
        self._proc: asyncio.subprocess.Process | None = None
        self._id = 0
        self._stderr_tail: list[str] = []
        self._stderr_task: asyncio.Task | None = None

    async def start(self) -> dict:
        """Launch the server and run the MCP initialize handshake."""
        self._proc = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
        )
        # Drain stderr in the background so a chatty server can't deadlock on a
        # full pipe; keep the last few lines for error messages.
        self._stderr_task = asyncio.ensure_future(self._drain_stderr())

        info = await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "tiles-ai", "version": "0.0.1"},
            },
        )
        await self._notify("notifications/initialized", {})
        return info

    async def list_tools(self) -> list[dict]:
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        return await self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )

    async def stop(self) -> None:
        if self._proc is None:
            return
        if self._stderr_task is not None:
            self._stderr_task.cancel()
        try:
            self._proc.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._proc.kill()
        self._proc = None

    # --- internals ---------------------------------------------------------

    async def _drain_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        while True:
            line = await self._proc.stderr.readline()
            if not line:
                break
            self._stderr_tail.append(line.decode("utf-8", "replace").rstrip())
            self._stderr_tail = self._stderr_tail[-20:]

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def _write(self, message: dict) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def _notify(self, method: str, params: dict) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: dict) -> dict:
        req_id = self._next_id()
        await self._write(
            {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        )
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            try:
                raw = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=_READ_TIMEOUT
                )
            except asyncio.TimeoutError as exc:
                raise MCPError(
                    f"timed out waiting for response to '{method}'"
                    + self._stderr_hint()
                ) from exc
            if not raw:
                raise MCPError(
                    f"MCP server exited before responding to '{method}'"
                    + self._stderr_hint()
                )
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue  # not a JSON-RPC line (stray output); skip
            if data.get("id") != req_id:
                continue  # a notification or another response; skip
            if "error" in data:
                raise MCPError(f"{method} failed: {data['error']}")
            return data.get("result", {})

    def _stderr_hint(self) -> str:
        if not self._stderr_tail:
            return ""
        return " | server stderr: " + " ".join(self._stderr_tail[-3:])


class MCPConnector(Connector):
    """Connector backed by a live MCP server, driven by its manifest."""

    def __init__(self, manifest: ConnectorManifest) -> None:
        super().__init__(manifest.id)
        self.manifest = manifest
        self._client: StdioMCPClient | None = None

    @classmethod
    def from_manifest(cls, manifest: ConnectorManifest) -> "MCPConnector":
        return cls(manifest)

    async def connect(self, auth: AuthConfig) -> Session:
        if not self.manifest.endpoint:
            raise MCPError(f"connector '{self.manifest_id}' has no endpoint command")

        # Credential hook: the manifest names the env vars the server needs (not
        # their values). Fail fast with a clear message if any is unset; the
        # launched server inherits the host environment, so set ones are passed
        # through automatically. Secrets never touch the manifest.
        missing = [name for name in auth.env if not os.environ.get(name)]
        if missing:
            raise MCPError(
                f"connector '{self.manifest_id}' needs environment variable(s) "
                f"{missing} set before it can connect. Export them and retry."
            )

        command = shlex.split(self.manifest.endpoint)
        self._client = StdioMCPClient(command)
        await self._client.start()
        return Session(connector_id=self.manifest_id, connected=True)

    async def list_tools(self) -> list[ToolSpec]:
        # The manifest is the authority on the surface tiles draw from (it's what
        # the registry validated). Use live_tools() to introspect the server.
        return list(self.manifest.tools)

    async def live_tools(self) -> list[ToolSpec]:
        """Introspect the running server's tools (for authoring/sync, not gating).

        Derives `side_effect` from the MCP `readOnlyHint` annotation, failing
        safe: a tool with no read-only hint is treated as side-effectful.
        """
        if self._client is None:
            raise MCPError("connector is not connected")
        specs: list[ToolSpec] = []
        for tool in await self._client.list_tools():
            annotations = tool.get("annotations") or {}
            read_only = bool(annotations.get("readOnlyHint", False))
            specs.append(
                ToolSpec(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    side_effect=not read_only,
                    input_schema=tool.get("inputSchema"),
                )
            )
        return specs

    async def call_tool(self, name: str, args: dict, context: CallContext) -> ToolResult:
        if self._client is None:
            raise MCPError("connector is not connected")

        spec = self.manifest.get_tool(name)
        side_effect = bool(spec.side_effect) if spec else True  # unknown -> fail safe
        if spec is None:
            return ToolResult(
                ok=False,
                error=f"connector '{self.manifest_id}' has no tool '{name}'",
                side_effect=side_effect,
            )

        try:
            result = await self._client.call_tool(name, args)
        except MCPError as exc:
            return ToolResult(ok=False, error=str(exc), side_effect=side_effect)

        text = _content_text(result.get("content", []))
        if result.get("isError"):
            return ToolResult(ok=False, error=text, side_effect=side_effect)
        return ToolResult(ok=True, output=text, side_effect=side_effect)

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.stop()
            self._client = None


def _content_text(content: list[dict]) -> Any:
    """Flatten MCP tool-result content blocks to text (the common case)."""
    parts = [block.get("text", "") for block in content if block.get("type") == "text"]
    return "\n".join(parts) if parts else content
