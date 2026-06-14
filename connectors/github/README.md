# GitHub connector (MCP)

A real `kind: mcp` connector over the official
[`@modelcontextprotocol/server-github`](https://github.com/modelcontextprotocol/servers).

## Setup

1. Create a GitHub personal access token with the scopes you need (read for the
   read-only tiles; `repo` for commenting/creating).
2. Export it before starting Tiles AI:
   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_…
   TILES_BRAIN=brain.local.yaml python -m tiles_ai.api
   ```
3. `npx` must be available (the connector launches the server with it).

Until the token is set, tiles bound to this connector show **needs token** on the
board and won't activate. The token is passed through to the server and is never
stored by Tiles AI.

## Tiles

- [github-triage](../../tiles/github-triage) — read_only: triage a repo's open issues.
- [github-comment](../../tiles/github-comment) — draft: draft an issue comment, queued for approval.

The `tools` surface in the manifest follows the official server; adjust it if
your server version exposes different names.
