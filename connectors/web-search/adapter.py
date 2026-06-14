"""Web Search connector adapter — the Brave Search MCP server via MCPConnector.

Set BRAVE_API_KEY in the host environment (declared in the manifest's auth.env);
it is passed through to the launched server and never stored by Tiles AI.
"""

from __future__ import annotations

from tiles_ai.connectors import MCPConnector


class WebSearch(MCPConnector):
    """Web search via the Brave Search MCP server. Needs npx + BRAVE_API_KEY."""
