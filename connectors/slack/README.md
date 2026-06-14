# Slack connector (MCP)

A real `kind: mcp` connector over the official
[`@modelcontextprotocol/server-slack`](https://github.com/modelcontextprotocol/servers).

## Setup

1. Create a Slack app, install it to your workspace, and copy the **Bot User
   OAuth Token** (`xoxb-…`) and your **Team ID** (`T…`).
2. Export both before starting Tiles AI:
   ```bash
   export SLACK_BOT_TOKEN=xoxb-…
   export SLACK_TEAM_ID=T0123456
   python -m tiles_ai.api
   ```
3. `npx` must be available.

Until both are set, tiles bound here show **needs token** and won't activate.

## Tiles

- [slack-catchup](../../tiles/slack-catchup) — read_only: summarize recent channel activity.
- [slack-drafter](../../tiles/slack-drafter) — draft: draft a message, queued for approval.
