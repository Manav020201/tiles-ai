"""Local-files connector adapter — a real MCP-backed connector.

All the logic is in `MCPConnector` (it speaks MCP over a stdio subprocess). This
adapter is just the concrete class the registry loads; swapping the manifest's
`endpoint` for a different MCP server is all it takes to back a different app.
"""

from __future__ import annotations

from tiles_ai.connectors import MCPConnector


class LocalFiles(MCPConnector):
    """Read-only filesystem access via the bundled example MCP server."""
