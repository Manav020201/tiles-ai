"""The Connector interface — `connectors/<id>/adapter.py` implements this.

A connector is the durable connection to one application. A tile never talks to
an app directly: it calls tools *through* its bound connector, and only the ones
in its `allowed_tools`. The MCP-backed connector is just one implementation of
this interface; the v0 mock is another. Because both satisfy the same protocol,
a real MCP connector drops in later without touching the tile contract.

Interfaces are async: connectors are I/O-bound (network, MCP, local servers) and
the runtime + FastAPI layer are async end to end.
"""

from __future__ import annotations

import abc
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .connector_manifest import AuthConfig, ToolSpec


class Session(BaseModel):
    """An established app connection. Opaque handle the connector owns.

    v0's mock returns a trivial session; a real connector stores transport
    handles, tokens, etc. The runtime treats it as opaque.
    """

    model_config = ConfigDict(extra="allow")

    connector_id: str
    connected: bool = True


class ToolResult(BaseModel):
    """The outcome of invoking one tool through a connector."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(description="Whether the tool call succeeded.")
    output: Any = Field(default=None, description="Tool return payload.")
    side_effect: bool = Field(
        default=False,
        description=(
            "Whether this call actually touched the outside world. Echoes the "
            "tool's declared `side_effect`; the gate relies on it."
        ),
    )
    error: str | None = Field(default=None, description="Error message when ok is False.")


class Connector(abc.ABC):
    """Base class every connector adapter implements.

    Keep an implementation readable end to end — a connector author should be
    able to copy the mock and swap three methods.
    """

    def __init__(self, manifest_id: str) -> None:
        self.manifest_id = manifest_id

    @abc.abstractmethod
    async def connect(self, auth: AuthConfig) -> Session:
        """Establish the app connection. Mocked in v0 (ignores auth)."""

    @abc.abstractmethod
    async def list_tools(self) -> list[ToolSpec]:
        """Return the app's tool surface (the superset tiles draw from)."""

    @abc.abstractmethod
    async def call_tool(
        self, name: str, args: dict, context: "CallContext"
    ) -> ToolResult:
        """Invoke one tool by name.

        Implementations MUST set `ToolResult.side_effect` to reflect whether the
        call touched the outside world (echo the tool's declared flag). The
        runtime routes only allow-listed tool names here.
        """

    async def disconnect(self) -> None:
        """Tear down the connection. Default no-op; override if you hold resources."""
        return None


class CallContext(BaseModel):
    """Context handed to a tool call: who is calling and under what grant.

    The connector does not enforce permissions (the gate does), but it receives
    enough context to log/scope the call.
    """

    model_config = ConfigDict(extra="forbid")

    tile_id: str
    allowed_tools: list[str] = Field(default_factory=list)
