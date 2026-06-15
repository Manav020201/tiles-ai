"""The connector layer.

v0 ships a generic, manifest-driven `MockConnector`. A reference connector's
`adapter.py` subclasses it and wires canned responses — no real network, no
credentials. A real MCP-backed connector is a future sibling implementation of
the same `tiles_ai.contracts.Connector` interface and drops in without touching
the tile contract.
"""

from __future__ import annotations

from .mcp import (
    MCPConnector,
    MCPError,
    StdioMCPClient,
    StreamableHttpMCPClient,
    introspect,
)
from .mock import MockConnector

__all__ = [
    "MockConnector",
    "MCPConnector",
    "MCPError",
    "StdioMCPClient",
    "StreamableHttpMCPClient",
    "introspect",
]
