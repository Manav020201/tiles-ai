# Web Search connector (MCP)

A real `kind: mcp` connector over
[`@modelcontextprotocol/server-brave-search`](https://github.com/modelcontextprotocol/servers).

## Setup

1. Get a Brave Search API key (https://brave.com/search/api/).
2. `npx` must be available (Node 18+).
3. Add the key. **Easiest — from the board:** open a Web Search tile (or 🔌 → ⚙
   on the connector) and paste `BRAVE_API_KEY`. It's saved locally in
   `secrets.local.yaml` (gitignored) and applied to the server's environment.

   Or export it before starting Tiles AI:
   ```bash
   export BRAVE_API_KEY=...
   tiles up
   ```

Until the key is set, tiles bound here show **needs token** and won't activate.
The key passes through to the launched server and never leaves your machine.

## Tiles

- [web-search](../../tiles/web-search) — read_only: search the web and digest the results.
- [research](../../tiles/research) — read_only: answer a question, grounded in web sources.
