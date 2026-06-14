"""GitHub connector adapter — the official GitHub MCP server via MCPConnector.

All logic is in MCPConnector. Set GITHUB_PERSONAL_ACCESS_TOKEN in the host
environment (declared in the manifest's auth.env); it is passed through to the
launched server, never stored by Tiles AI.
"""

from __future__ import annotations

from tiles_ai.connectors import MCPConnector


class GitHub(MCPConnector):
    """GitHub via its MCP server. Needs npx + GITHUB_PERSONAL_ACCESS_TOKEN."""
