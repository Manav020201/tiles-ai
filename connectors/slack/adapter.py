"""Slack connector adapter — the official Slack MCP server via MCPConnector.

Set SLACK_BOT_TOKEN and SLACK_TEAM_ID in the host environment (declared in the
manifest's auth.env). They are passed through to the launched server and never
stored by Tiles AI.
"""

from __future__ import annotations

from tiles_ai.connectors import MCPConnector


class Slack(MCPConnector):
    """Slack via its MCP server. Needs npx + SLACK_BOT_TOKEN + SLACK_TEAM_ID."""
