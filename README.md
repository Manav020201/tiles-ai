# Tiles AI

A phone-home-screen for your AI agents. A **board** is a grid of **tiles**; each
tile is an agent. Tap a tile and it turns **green** — running. Tiles AI is the
control plane around your agents: **register → activate → observe → permission →
(later) compose.** It is *not* another framework for writing agent logic — a
tile can wrap LangGraph, CrewAI, the OpenAI Agents SDK, or plain Python.

> **Status: v0, phases 1–4 done.** The contract, registry/loader, runtime stack
> (mock connector, model adapter, permission gate + approval queue), and the
> FastAPI control-plane API with an SSE event stream are in — plus `read_only`
> and `draft` reference tiles on a shared connector, and 84 tests. The React
> board is next. See [`SPEC.md`](SPEC.md).

## Run the API

```bash
pip install -e ".[dev]"
python -m tiles_ai.api            # serves http://127.0.0.1:8000
```

Endpoints: `GET /api/tiles`, `POST /api/tiles/{id}/{activate,deactivate,run}`,
`GET /api/approvals`, `POST /api/approvals/{id}/resolve`, `GET/POST /api/providers`,
`POST /api/providers/{id}/test`, `PUT /api/brain/default`, and `GET /api/events`
(SSE). The brain store loads from `brain.local.yaml` (gitignored).

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
