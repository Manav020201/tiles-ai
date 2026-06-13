# Tiles AI

A phone-home-screen for your AI agents. A **board** is a grid of **tiles**; each
tile is an agent. Tap a tile and it turns **green** — running. Tiles AI is the
control plane around your agents: **register → activate → observe → permission →
(later) compose.** It is *not* another framework for writing agent logic — a
tile can wrap LangGraph, CrewAI, the OpenAI Agents SDK, or plain Python.

> **Status: v0, phases 1–5 done.** The contract, registry/loader, runtime stack
> (mock connector, model adapter, permission gate + approval queue), the FastAPI
> control-plane API with an SSE event stream, and the React board (onboarding,
> activation, badges, approvals, live feed, brain override) are all in — plus
> `read_only` and `draft` reference tiles on a shared connector, and 85 backend
> tests. Docs + license are the last step. See [`SPEC.md`](SPEC.md).

## Run it

```bash
pip install -e ".[dev]"

# zero-setup demo: an offline echo brain, no keys, no network
TILES_ECHO=1 python -m tiles_ai.api        # API on http://127.0.0.1:8000

# the board (in another shell)
cd frontend && npm install && npm run dev  # http://localhost:5173
```

Drop `TILES_ECHO=1` to use a real brain; the store loads from `brain.local.yaml`
(gitignored) and the board's onboarding writes it.

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

A connector is, in the general case, a binding to an app's **MCP** server. v0
ships a `mock` connector; a real MCP-backed one drops in without changing the
tile contract.

## Develop

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The whole contract is in [`src/tiles_ai/contracts/`](src/tiles_ai/contracts/).
Start with [`SPEC.md`](SPEC.md), then read the modules in this order:
`lifecycle` → `permissions` → `connector_manifest` → `tile_manifest` →
`provider_config` → `connector` → `tile` → `validation`.

## License

To be decided in phase 6 (MIT vs Apache-2.0).
