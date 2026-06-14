# Tiles AI

A phone-home-screen for your AI agents. A **board** is a grid of **tiles**; each
tile is an agent. Tap a tile and it turns **green** — running. Tiles AI is the
control plane around your agents: **register → activate → observe → permission →
(later) compose.** It is *not* another framework for writing agent logic — a
tile can wrap LangGraph, CrewAI, the OpenAI Agents SDK, or plain Python.

[![CI](https://github.com/manavsinghai/tiles-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/manavsinghai/tiles-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Status: v0 complete.** The contract, registry/loader, runtime stack (mock
> connector, model adapter, permission gate + approval queue), the FastAPI
> control-plane API with an SSE event stream, and the React board (onboarding,
> activation, badges, approvals, live feed, brain override) are all in — plus
> `read_only` and `draft` reference tiles on a shared connector, and 85 backend
> tests. See [`SPEC.md`](SPEC.md) for the full spec.

**Docs:** [SPEC.md](SPEC.md) (the contract) · [docs/AUTHORING.md](docs/AUTHORING.md)
(write a tile or connector) · [CONTRIBUTING.md](CONTRIBUTING.md) ·
[frontend/](frontend/) (the board)

## Run it

Once published, the whole app (API + board) runs on one port:

```bash
pipx install tiles-ai     # or: pip install tiles-ai
tiles up --echo           # offline demo brain, no keys → http://127.0.0.1:8000
tiles up                  # real brain (onboarding writes brain.local.yaml)
```

From a clone (with the board hot-reloading):

```bash
pip install -e ".[dev]"
tiles up --echo                            # API on http://127.0.0.1:8000
cd frontend && npm install && npm run dev  # board on http://localhost:5173
```

Other commands: `tiles list` (show discovered tiles/connectors), `tiles new <id>`
(scaffold a tile). See [docs/AUTHORING.md](docs/AUTHORING.md).

**Starter board.** Five **instant** tiles work the moment a brain is connected —
no app, no credentials: [Ask](tiles/ask), [Summarize](tiles/summarize),
[Translate](tiles/translate), [Extract](tiles/extract),
[Brainstorm](tiles/brainstorm). Two app tiles on a shared (mock) Gmail connector
show the read vs. draft flow: [Inbox Summary](tiles/inbox-summary) (read_only) and
[Reply Drafter](tiles/reply-drafter) (draft, queues for approval).

API endpoints: `GET /api/tiles`, `POST /api/tiles/{id}/{activate,deactivate,run}`,
`PUT /api/tiles/{id}/brain`, `GET /api/approvals`, `POST /api/approvals/{id}/resolve`,
`GET/POST /api/providers`, `POST /api/providers/{id}/test`, `PUT /api/brain/default`,
and `GET /api/events` (SSE). See [`frontend/`](frontend/) for the board.

## Why it exists

- **A tile is a contract, not a UI element.** The center of the project is a
  minimal, inspectable spec every tile satisfies.
- **Permissions are first-class.** Every tile declares a permission tier. Any
  real-world side effect defaults to human-in-the-loop. Green ≠ unsupervised.
- **Connect the brain once.** Configure an LLM provider once (hosted API or a
  local endpoint like Ollama); every tile uses it by default.
- **Inspectability is the win.** Read one reference tile end to end, copy the
  folder, implement one interface, done.

## The contract at a glance

```
Connector  = durable connection to one app (auth + tool surface). One per app.
Tile       = an agent on top: model + instructions + permission tier,
             bound to one connector, allow-listed to a subset of its tools.
Brain      = one global model provider config; tiles use it unless they pin one.
```

A connector is, in the general case, a binding to an app's **MCP** server. Both
a `mock` connector and a real **MCP-backed** one ship today — and they satisfy
the same interface, so tiles binding either are identical. The
[local-files connector](connectors/local-files) is real: it launches an MCP
server over stdio, and [Ask My Files](tiles/ask-my-files) reads your documents
through it. Point its `endpoint` at any MCP server (`npx … server-filesystem`,
GitHub, Slack, …) and the tiles are unchanged.

**App packs.** Premade connectors + tiles ship for [GitHub](connectors/github)
(triage issues, draft a comment), [Slack](connectors/slack) (catch up, draft a
message), and [Web Search](connectors/web-search) (search, research). They run on
the official MCP servers — set the connector's token
(e.g. `GITHUB_PERSONAL_ACCESS_TOKEN`) and the board enables them; until then they
show **needs token**. A connector's manifest names the env vars it needs (never
the values); they pass through to the server and are never stored by Tiles AI.

## Architecture

```
   React board  ──HTTP/SSE──▶  FastAPI control plane
                                     │
                                     ▼
   registry ──▶ runtime ──▶ permission gate ──▶ connector ──▶ app (mock | MCP)
                  │                                 ▲
                  ▼                                 │
            model adapter ──▶ brain (Anthropic / OpenAI / Ollama / echo)
```

- **registry** discovers and validates `connectors/` and `tiles/`, rejecting any
  tile that binds a missing connector or tool.
- **runtime** activates tiles, assembles their context, and routes tool calls.
- **permission gate** is the single path a side effect can take — read_only
  rejects, draft queues for approval, autonomous executes.
- **model adapter** resolves each tile's brain (its pin, else the global default)
  and runs completions.

## Authoring a tile

Copy a folder, implement one method:

```python
from tiles_ai.contracts import ActionPlan, Tile

class MyTile(Tile):
    async def run(self, input, context) -> ActionPlan:
        data = await context.tools.call("list_messages")     # allow-listed read
        answer = await context.model.complete(f"Summarize: {data.output}")
        return ActionPlan(result=answer)                     # propose side effects, don't do them
```

Full walkthrough — including adding a connector — in
[docs/AUTHORING.md](docs/AUTHORING.md). The two reference tiles
([inbox-summary](tiles/inbox-summary), [reply-drafter](tiles/reply-drafter)) are
meant to be read end to end and copied.

## Out of scope for v0 (seams left, not built)

Multi-tile orchestration (the `provides`/`consumes` seam is declared) · scheduled
/ event triggers (activation is manual) · multi-user / hosting / marketplace ·
real OAuth (the `auth` hook is declared) · live MCP servers (the `Connector`
interface is the abstraction; a mock ships today).

## Develop

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The whole contract is in [`src/tiles_ai/contracts/`](src/tiles_ai/contracts/).
Start with [`SPEC.md`](SPEC.md), then read the modules in this order:
`lifecycle` → `permissions` → `connector_manifest` → `tile_manifest` →
`provider_config` → `connector` → `tile` → `validation`. See
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## License

[MIT](LICENSE).
