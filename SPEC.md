# Tiles AI — Specification (v0)

> This document is the spine of the project. The board, the runtime, the docs,
> and future multi-tile collaboration are all downstream of the contract
> defined here. The executable truth lives in `src/tiles_ai/contracts/`; this
> file is its prose companion. When the two disagree, the code wins and this
> file is the bug.

## Mental model

A board is a grid of tiles, like a phone home screen. Each tile is an AI agent.
Tapping a tile activates it — it turns **green** = running. "Green" means
*running*, not *unsupervised*.

The board is a **control plane**, not an authoring framework. We do not compete
with LangGraph / CrewAI / the OpenAI Agents SDK on writing agent logic — a tile
may wrap any of those, or plain Python. Our value is the layer they are weak at:
**register → activate → observe → permission → (later) compose.** The agent's
internal logic is a black box behind the contract.

## The two primitives

The primitive is **one tile, one application**. To keep that clean, the concept
splits into two layers:

| Layer | What it is | Lifetime |
|-------|-----------|----------|
| **Connector** | The durable, reusable connection to an application: its auth and its tool surface. One per app. | Heavy, slow-changing. |
| **Tile** | The agent on top: model + instructions + permission tier, bound to one connector and allow-listed to a subset of its tools. | Light, fast-changing. |

Many tiles can bind to one connector (a read-only "summarize inbox" tile and a
"draft replies" tile both bind to one Gmail connector). The heavy thing is the
app connection, not the prompt — so we build the seam now. Folding tools
straight into a tile would force re-auth per tile and block the
"many tiles over one app" pattern.

In the general case a connector is a binding to an app's **MCP** server. v0
ships a `mock` connector; the interface is shaped so a real MCP-backed connector
drops in **unchanged**.

## Repository layout

```
connectors/<connector_id>/
  manifest.yaml      # app id, auth config, tool surface (MCP ref or mock)
  adapter.py         # implements the Connector interface

tiles/<tile_id>/
  manifest.yaml      # declarative spec (binds to a connector)
  handler.py         # implements the Tile interface
  README.md          # what this tile does + how to configure it

src/tiles_ai/
  contracts/         # THIS SPEC, as code (phase 1)
  # registry, runtime, connectors, permission_gate, model_adapter,
  # events, api  — phases 2-4

tests/               # contract tests (phase 1), then per-layer tests
frontend/            # React board (phase 5)
```

## Connector manifest (`connectors/<id>/manifest.yaml`)

Schema: `tiles_ai.contracts.ConnectorManifest`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | slug | Stable, e.g. `gmail`. Tiles bind to this. |
| `app` | string | Display name, e.g. `Gmail`. |
| `kind` | `mcp` \| `mock` \| `custom` | How it talks to the app. |
| `endpoint` | string? | MCP server URL/ref. **Required when `kind: mcp`.** |
| `auth` | `{ scheme, scopes[] }` | Auth scheme + scopes. **Mocked in v0.** |
| `tools` | `ToolSpec[]` | The app's tool surface — the superset tiles draw from. |

`ToolSpec = { name, description, side_effect: bool, input_schema? }`. The
connector is the **authority** on `side_effect`: it declares whether invoking a
tool touches the outside world. The permission gate trusts this flag — setting
it correctly is a safety-critical responsibility of the connector author.

## Tile manifest (`tiles/<id>/manifest.yaml`)

Schema: `tiles_ai.contracts.TileManifest`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | slug | Stable, unique, e.g. `gmail-draft`. |
| `name` | string | Display name. |
| `description` | string | One line, shown on the board. |
| `icon` | string | Emoji or asset ref. |
| `connector` | slug? | Connector id this tile binds to. **Omit for instant tiles.** |
| `model` | `ModelRef`? | Pinned model. **Omit to use the global default brain.** |
| `instructions` | string | System prompt / role for the agent. |
| `allowed_tools` | slug[] | Allow-list: subset of the connector's tools this tile may call. |
| `permission_tier` | `read_only` \| `draft` \| `autonomous` | See below. |
| `provides` | `Capability[]` | What this tile exposes to the system / other tiles. *(composition seam)* |
| `consumes` | `Capability[]` | What it expects as input. *(composition seam)* |

`ModelRef = { provider, model, endpoint? }` and is **secret-free by
construction** — manifests get checked into repos, so they never carry an API
key. Credentials are resolved at run time from the local brain store.

Two deliberate shapes:

- **`connector` is optional.** Instant tiles (Ask, Summarize) need no app — they
  prove the brain works in ~10 seconds with zero setup. The first thing a user
  does must not be an auth screen. A tile with no connector may not allow-list
  any tools (enforced).
- **`model` is optional.** A tile with no model uses the global default brain.
  This is what lets a beginner connect once and never configure a model per
  tile.

## Permission tiers

Permissions are **first-class**. Every tile declares a `permission_tier`. Any
action with a real-world side effect defaults to human-in-the-loop.

| Tier | Meaning | Side-effect action becomes |
|------|---------|----------------------------|
| `read_only` | Reads/reports; never causes side effects. | **REJECT** (tier violation) |
| `draft` | Produces side-effectful actions, queued for approval. | **QUEUE** |
| `autonomous` | May execute approved side effects directly (opt-in). | **EXECUTE** if approved, else **QUEUE** |

A non-side-effectful action always **EXECUTEs**, regardless of tier. The single
source of truth for this policy is `permissions.evaluate(tier, is_side_effect,
approved=…)`. The permission gate (phase 3) is the only caller — it stays dumb
and auditable.

## Lifecycle (state machine)

```
defined ─► available ─► active ─┬─► paused ─► active
                                └─► stopped ─► available
                                              (composed: reserved)
```

| State | Meaning |
|-------|---------|
| `defined` | Manifest exists on disk; not yet validated/loaded. |
| `available` | Validated, dependencies satisfied, loaded by the registry, idle. |
| `active` | User activated it (green); runtime executing/listening. |
| `paused` | Temporarily suspended; resumable. |
| `stopped` | Deactivated and torn down; can be made available again. |
| `composed` | **Reserved** for multi-tile collaboration. Unreachable in v0. |

Legal transitions are enforced by `lifecycle.transition()`. `composed` has no
inbound or outbound edges yet — it exists so future work has one obvious place
to wire in.

## Interfaces

Both interfaces are **async** — connectors are I/O-bound (network, MCP, local
servers) and the runtime + API are async end to end.

### Connector (`connectors/<id>/adapter.py`)

```python
class Connector(abc.ABC):
    async def connect(self, auth: AuthConfig) -> Session: ...
    async def list_tools(self) -> list[ToolSpec]: ...
    async def call_tool(self, name, args, context: CallContext) -> ToolResult: ...
    async def disconnect(self) -> None: ...   # default no-op
```

A tile never talks to an app directly — it calls tools through its bound
connector, and only the ones in its `allowed_tools`. The MCP connector and the
mock are both just implementations of this interface. `call_tool` MUST set
`ToolResult.side_effect` to reflect whether the call touched the outside world.

### Tile (`tiles/<id>/handler.py`)

```python
class Tile(abc.ABC):
    async def validate(self, ctx: RunContext) -> ValidationResult: ...  # default pass
    async def on_activate(self, ctx: RunContext) -> None: ...           # default no-op
    async def run(self, input, ctx: RunContext) -> ActionPlan: ...      # required
    async def on_deactivate(self) -> None: ...                          # default no-op
```

`run` returns an **`ActionPlan`** = `{ result, actions: ProposedAction[] }`.
Each `ProposedAction` carries a `side_effect` flag. **The handler never executes
side effects itself** — it *proposes* them, and the permission gate decides per
the tile's tier. This is what makes "green = running, not unsupervised" a
structural guarantee rather than a convention.

## The brain layer (model provider config)

**Connect the brain once.** A user configures an LLM provider once; every tile
uses that default unless it pins its own. Schema:
`tiles_ai.contracts.BrainConfig`.

- `providers[]` — each is one of:
  - **hosted**: `{ id, kind: hosted, provider, api_key, model }`
  - **local**: `{ id, kind: local, endpoint, model }` (Ollama / any local server)
- `default_provider` — id of the global default brain.

**Keys are stored locally only.** The app runs on the user's machine; keys never
leave it and are never sent to any project-owned server. `BrainConfig` is the
secret-holding store; tile manifests are secret-free.

**Resolution order:** tile's pinned `model` → else `default_provider`. Implemented
by `resolve_brain(tile_model, config) -> ResolvedBrain`. A tile with no pin and
no default configured raises `BrainResolutionError` — the case onboarding exists
to prevent.

`ResolvedBrain.source` is what the board's brain badge shows: `default` or
`pinned`. Each provider also gets a **Test** action (phase 3) — a trivial
completion returning ok/error — so the user gets a green check before relying on
it.

## What v0 builds the seam for, but does not implement

- **Multi-tile collaboration / orchestration.** The contract declares
  `provides`/`consumes`; nothing consumes them yet.
- **Scheduled / event triggers.** v0 activation is manual only.
- **Multi-user, accounts, hosted deployment, marketplace.**
- **Real OAuth.** Reference tiles use mock side effects / simple keys. `AuthConfig`
  is the declared hook for real auth.
- **Live MCP servers.** The `Connector` interface is the abstraction; v0 ships a
  mock. A real MCP connector drops in without changing the tile contract.

## Build order

1. **Spec + skeleton** — manifests, brain schema, interfaces, lifecycle,
   permission tiers as documented code + this SPEC + contract tests. **← you are here.** _Pause for review._
2. Registry + loader.
3. Connector layer (mock) + runtime + permission gate + model_adapter +
   one `read_only` reference tile.
4. FastAPI endpoints + event stream + a `draft` reference tile + approval queue.
5. React board UI (onboarding, activation, badges, activity feed, approvals,
   brain override).
6. Docs + license.
```
