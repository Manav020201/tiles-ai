"""A generic, manifest-driven mock connector.

The mock fakes an application's tool surface in-process: `list_tools` comes
straight from the manifest, and `call_tool` returns a canned response the
connector author registers per tool. It exists so reference tiles run with zero
credentials and no running server, while still exercising the real
connector → tool-call → result path.

A reference connector's `adapter.py` subclasses this and registers responses:

    from tiles_ai.connectors import MockConnector

    class GmailMock(MockConnector):
        def __init__(self, manifest):
            super().__init__(manifest)
            self.set_response("list_messages", [{"from": "a@b.com", "subject": "Hi"}])
            self.set_response("send_message", lambda args: {"status": "sent (mock)", **args})

Crucially, the mock still reports each tool's declared `side_effect` on the
result, so the permission gate behaves exactly as it will against a real
connector.
"""

from __future__ import annotations

from collections.abc import Callable
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

# A response is either a static value or a callable that maps args -> value.
Responder = Any | Callable[[dict], Any]


class MockConnector(Connector):
    """In-process connector driven by its manifest's tool surface."""

    def __init__(self, manifest: ConnectorManifest) -> None:
        super().__init__(manifest.id)
        self.manifest = manifest
        self._responses: dict[str, Responder] = {}
        self._connected = False

    @classmethod
    def from_manifest(cls, manifest: ConnectorManifest) -> MockConnector:
        # The mock needs the whole manifest (its tool surface), not just the id.
        return cls(manifest)

    def set_response(self, tool: str, value: Responder) -> None:
        """Register the canned output for a tool (static value or args->value fn)."""
        self._responses[tool] = value

    async def connect(self, auth: AuthConfig) -> Session:
        # v0: auth is mocked. A real connector runs its auth flow here.
        self._connected = True
        return Session(connector_id=self.manifest_id, connected=True)

    async def list_tools(self) -> list[ToolSpec]:
        return list(self.manifest.tools)

    async def call_tool(self, name: str, args: dict, context: CallContext) -> ToolResult:
        spec = self.manifest.get_tool(name)
        if spec is None:
            return ToolResult(
                ok=False,
                error=f"connector '{self.manifest_id}' has no tool '{name}'",
                side_effect=False,
            )

        responder = self._responses.get(name)
        if callable(responder):
            output = responder(args or {})
        elif responder is not None:
            output = responder
        else:
            # No canned response registered: echo the call so the path still works.
            output = {"mock": True, "tool": name, "args": args or {}}

        # Echo the declared side-effect flag — the gate relies on it.
        return ToolResult(ok=True, output=output, side_effect=spec.side_effect)

    async def disconnect(self) -> None:
        self._connected = False
