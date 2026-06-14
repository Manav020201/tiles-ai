# Web Search connector (MCP)

A real `kind: mcp` connector over
[`@modelcontextprotocol/server-brave-search`](https://github.com/modelcontextprotocol/servers).

## Setup

1. Get a Brave Search API key (https://brave.com/search/api/).
2. Export it before starting Tiles AI:
   ```bash
   export BRAVE_API_KEY=...
   tiles up
   ```
3. `npx` must be available.

Until the key is set, tiles bound here show **needs token** and won't activate.
The key passes through to the server and is never stored by Tiles AI.

## Tiles

- [web-search](../../tiles/web-search) — read_only: search the web and digest the results.
- [research](../../tiles/research) — read_only: answer a question, grounded in web sources.
