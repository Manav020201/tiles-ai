# Tiles AI

A phone-home-screen for your AI agents. A **board** is a grid of **tiles**; each
tile is an agent. Tap a tile and it turns **green** — running. Tiles AI is the
control plane around your agents: **register → activate → observe → permission →
(later) compose.** It is *not* another framework for writing agent logic — a
tile can wrap LangGraph, CrewAI, the OpenAI Agents SDK, or plain Python.

[![CI](https://github.com/Manav020201/tiles-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Manav020201/tiles-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

![Tiles AI — a home screen for your AI agents](docs/hero.svg)

> **Status: v0.1.0** (unreleased work on `main`). The whole stack is in: the tile
> contract, registry, runtime + permission gate + approval queue, a FastAPI
> control plane with an SSE stream, and an iOS-style React board you can author
> **entirely from the UI** — create / edit / delete tiles and connectors, connect
> any app by its MCP command, manage brains (cloud or Ollama), watch live
> activity. Plus a real **MCP-backed connector**, app packs (GitHub · Slack · Web
> Search · local files), instant tiles, and a `tiles` CLI with `--reload`.
> Connectors speak MCP over **stdio or HTTP**; tiles can **chain** (provides →
> consumes), run on a **schedule**, and connect via **OAuth** or env vars.
> **180 tests** (165 backend, 15 frontend) and CI on Python 3.11/3.12. See
> [`SPEC.md`](SPEC.md) for the full spec.

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
(scaffold a tile), `tiles up --reload` (hot-reload while you edit). See
[docs/AUTHORING.md](docs/AUTHORING.md).

> The image above is an illustration. To record a real demo GIF, run
> `tiles up --echo` and capture the board with any screen recorder.

**Starter board — useful with zero credentials.** Five **instant** tiles work the
moment a brain is connected: [Ask](tiles/ask), [Summarize](tiles/summarize),
[Translate](tiles/translate), [Extract](tiles/extract),
[Brainstorm](tiles/brainstorm). A **local files** pack makes your own machine
smart, no API keys: [Ask My Files](tiles/ask-my-files),
[Summarize Folder](tiles/summarize-folder), [Find Files](tiles/find-files), and
[Tidy Folder](tiles/tidy-folder) — which *proposes* sorting your files into
folders and moves them only after you approve each one. (App packs like Gmail,
GitHub, Slack, and Web Search add more once you provide a token.)

## Build agents without leaving the board

The board is the on-ramp to agent engineering — every authoring action is in the UI:

- **＋ New tile** — fill a short form; the tile is scaffolded (`manifest.yaml` +
  `handler.py`) and appears live, no restart. Open the generated handler to go deeper.
- **🔌 New app** — paste an app's MCP server command; Tiles launches it, reads its
  tools automatically, and scaffolds the connector. It's then bindable by any tile.
- **Edit / delete** — tap a tile to edit its manifest or delete it; ⚙ a connector
  group to rename it, re-fetch tools, or disconnect (refused while tiles use it).
- **🧠 Brains** — add a cloud LLM or a local Ollama model, set the default, or test
  it, any time — not just first-launch onboarding.
- **Run · approve · observe** — tap to run; `draft` actions queue for approval;
  each tile shows its recent activity; tiles/connectors that fail to load surface
  their reason inline.
- **Hot reload** — `tiles up --reload` re-discovers as you edit files (`*.py` and
  `*.yaml`), or hit the ⟳ button.

Prefer code? Everything above is just folders under `tiles/` and `connectors/` —
see [docs/AUTHORING.md](docs/AUTHORING.md).

**API.** The board is a thin client over a REST + SSE API (interactive docs at
`/docs`): tiles (list, create / edit / delete, activate / run / deactivate, pin a
brain), connectors (list, introspect, create / edit / delete), approvals,
providers (add / remove / test, set default), `GET /api/errors`, `POST /api/reload`,
and `GET /api/events` (SSE).

## Why it exists

- **A tile is a contract, not a UI element.** The center of the project is a
  minimal, inspectable spec every tile satisfies.
- **Permissions are first-class.** Every tile declares a permission tier. Any
  real-world side effect defaults to human-in-the-loop. Green ≠ unsupervised.
- **Connect the brain once.** Configure an LLM once (hosted API or a local
  endpoint like Ollama); every tile uses it by default. Manage brains any time
  from the 🧠 panel; a tile can pin its own.
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
through it. Point its `endpoint` at any MCP server and the tiles are unchanged —
a local launch command (`npx … server-filesystem`) **or** an `http(s)://` URL for
a remote/hosted server (Streamable HTTP transport, bearer-token auth).

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

…or skip the editor and do it from the board (see
[above](#build-agents-without-leaving-the-board)) — the form generates exactly
this. Full walkthrough, including adding a connector, in
[docs/AUTHORING.md](docs/AUTHORING.md). The two reference tiles
([inbox-summary](tiles/inbox-summary), [reply-drafter](tiles/reply-drafter)) are
meant to be read end to end and copied.

## Not built yet (seams left for later)

Richer multi-tile graphs (sequential `provides`→`consumes` flows ship; branching
/ fan-out later) · cron & event triggers (interval scheduling ships) · OAuth
refresh-token rotation (the authorization-code flow ships) · multi-user / hosting
/ marketplace.

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
