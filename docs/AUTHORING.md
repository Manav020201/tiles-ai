# Authoring guide

There are two things you can author in Tiles AI:

1. **A tile** — an agent: a model + instructions + a permission tier, optionally
   bound to one connector. This is the common case.
2. **A connector** — the durable connection to one application (its auth and its
   tool surface). You write one of these per app; many tiles share it.

The whole design optimizes for one workflow: **copy a folder, implement one
interface.** If you ever find yourself writing registration boilerplate or
wiring, stop — you're probably fighting the grain.

> Reference material: [`SPEC.md`](../SPEC.md) is the field-by-field contract. The
> two reference folders — [`tiles/inbox-summary`](../tiles/inbox-summary)
> (read_only) and [`tiles/reply-drafter`](../tiles/reply-drafter) (draft) — are
> meant to be read end to end and copied.

---

## Part 1 — Write a tile

### 1. Copy a reference folder

```bash
cp -r tiles/inbox-summary tiles/my-tile
```

A tile folder is exactly three files:

```
tiles/my-tile/
  manifest.yaml   # the declarative spec
  handler.py      # implements the Tile interface (one method: run)
  README.md       # what it does + how to configure it
```

### 2. Edit the manifest

```yaml
id: my-tile               # must equal the folder name
name: My Tile
description: One line shown on the board.
icon: "🔧"

connector: gmail          # omit entirely for an "instant" tile (no app)
allowed_tools: [list_messages]   # subset of the connector's tools you may call
permission_tier: read_only       # read_only | draft | autonomous

instructions: >
  The system prompt / role for the agent.

# model:                  # OMIT to use the global default brain (recommended).
#   provider: ollama      # Pin only when this tile needs a specific model.
#   model: llama3
#   endpoint: http://localhost:11434
```

Rules the registry enforces at load time (so mistakes fail loudly, early):

- `id` must match the folder name.
- `allowed_tools` may only list tools the bound connector actually exposes.
- A `read_only` tile may **not** allow-list a side-effectful tool.
- No `connector` ⇒ no `allowed_tools` (an instant tile touches no app).
- Omit `model` and the tile uses the user's default brain. Never put an API key
  in a manifest — manifests get committed; keys live only in the local brain store.

### 3. Implement `run`

`handler.py` defines one concrete `Tile` subclass. The only required method is
`run`; everything else has a sensible default.

```python
from tiles_ai.contracts import ActionPlan, Tile

class MyTile(Tile):
    async def run(self, input, context) -> ActionPlan:
        # READ through the connector. ctx.tools enforces your allow-list and
        # refuses side-effectful tools — you can only read here.
        data = await context.tools.call("list_messages")

        # CALL the brain. ctx.model is already bound to whatever brain resolved
        # for this tile (its pin, or the global default) — you don't pick.
        answer = await context.model.complete(
            f"Summarize: {data.output}",
            system=context.manifest.instructions,
        )

        return ActionPlan(result=answer)
```

What `context` (a `RunContext`) gives you — and deliberately does **not**:

| You get | You do NOT get |
|---|---|
| `ctx.manifest` — your resolved manifest | the raw connector (removed on purpose) |
| `ctx.tools.call(name, args)` — allow-listed reads | any way to fire a side effect inline |
| `ctx.model.complete(prompt, system=…)` — the brain | raw API keys |

This is the core safety property: a handler can only **read** (`ctx.tools`) and
**propose** (`ActionPlan`). It can never execute a side effect itself.

### 4. Side effects: propose, don't do

To send, post, or write anything, return a `ProposedAction` flagged
`side_effect=True`. You do not execute it — the permission gate does, according
to your tier.

```python
from tiles_ai.contracts import ActionPlan, ProposedAction, Tile

class MyDraftTile(Tile):
    async def run(self, input, context) -> ActionPlan:
        body = await context.model.complete("Draft a reply…")
        send = ProposedAction(
            tool="send_message",
            args={"to": "a@b.com", "body": body},
            side_effect=True,
            summary="Reply to a@b.com",   # shown in the approval queue
        )
        return ActionPlan(result={"draft": body}, actions=[send])
```

How the gate treats that action, by tier:

| Tier | Side-effectful action becomes |
|---|---|
| `read_only` | **rejected** (it's a tier violation — don't propose side effects) |
| `draft` | **queued** for human approval |
| `autonomous` | **executed** directly (the tier is the standing opt-in) |

Pick the lowest tier that does the job. `draft` is the right home for almost
anything that writes to the outside world.

### 5. Instant tiles (no connector)

Omit `connector` and `allowed_tools` entirely. `ctx.tools` will be `None`; you
just use `ctx.model`. This is how "Ask" / "Summarize" work — a win in ten seconds
with zero setup, and the first thing a new user should see.

These are so common there's a reusable base, `PromptTile`, that runs the input
through the brain using the manifest's `instructions`. Your handler becomes a
one-liner and the *manifest* is the tile:

```python
from tiles_ai.handlers import PromptTile

class Ask(PromptTile):
    """Behavior is entirely in manifest.yaml (instructions)."""
```

To take a freeform text input, declare it in `consumes` — the board renders an
input box and uses its `description` as the placeholder:

```yaml
consumes:
  - name: prompt
    description: Ask a question…
```

The shipped instant tiles ([ask](../tiles/ask), [summarize](../tiles/summarize),
[translate](../tiles/translate), [extract](../tiles/extract),
[brainstorm](../tiles/brainstorm)) are all PromptTile + a manifest — read one and
copy it. (Prefer writing `run` yourself for anything that reads from an app or
proposes side effects.)

### 6. Optional hooks

Override these only if you need them:

- `async def validate(self, context) -> ValidationResult` — extra load-time checks.
- `async def on_activate(self, context)` / `async def on_deactivate(self)` —
  set up / tear down resources around the green state.

### 7. Check it loads

Start the API and look at the board (or `curl`):

```bash
TILES_ECHO=1 python -m tiles_ai.api
curl -s localhost:8000/api/tiles | python -m json.tool
```

If your tile is missing, it failed validation — the reason is in the server log
(the registry collects per-tile errors instead of crashing the whole board).

---

## Part 2 — Add a connector

You only need this when your tile talks to an app no existing connector covers.

### 1. The folder

```
connectors/my-app/
  manifest.yaml   # app id, kind, auth, tool surface
  adapter.py      # implements the Connector interface
```

### 2. The manifest

```yaml
id: my-app                # must equal the folder name
app: My App
kind: mock                # mock | mcp | custom
# endpoint: https://…     # required when kind: mcp

auth:
  scheme: none            # mocked in v0; real auth plugs in here later
  scopes: []

tools:
  - name: list_things
    description: List things.
    side_effect: false    # a read — safe for read_only tiles
  - name: create_thing
    description: Create a thing.
    side_effect: true     # touches the world — gated behind approval
```

**The `side_effect` flag is safety-critical.** The connector is the single
authority on whether a tool touches the outside world; the permission gate trusts
it completely. Mark every writing/sending/deleting tool `side_effect: true`.

### 3. The adapter

For a `mock` connector, subclass `MockConnector` and register canned responses.
That's the entire adapter:

```python
from tiles_ai.connectors import MockConnector

class MyAppMock(MockConnector):
    def __init__(self, manifest):
        super().__init__(manifest)
        self.set_response("list_things", [{"id": 1, "name": "alpha"}])
        # A response can be a value or an args -> value function.
        self.set_response("create_thing", lambda args: {"created": args})
```

For a real connector (e.g. MCP-backed), implement the interface directly:

```python
from tiles_ai.contracts import Connector, Session, ToolResult, ToolSpec

class MyAppConnector(Connector):
    @classmethod
    def from_manifest(cls, manifest):
        return cls(manifest.id)            # or pass the whole manifest if you need it

    async def connect(self, auth) -> Session:
        ...                                # run your auth flow; return a Session

    async def list_tools(self) -> list[ToolSpec]:
        ...

    async def call_tool(self, name, args, context) -> ToolResult:
        # MUST set side_effect on the result to reflect whether the call
        # touched the world (echo the tool's declared flag).
        ...
```

The runtime instantiates every connector via `from_manifest`, connects it, and
routes a tile's allow-listed tool calls through it — your tile code is identical
whether it's the mock or the real thing.

### 4. Bind a tile to it

In a tile manifest: set `connector: my-app` and `allowed_tools` to the subset of
your tool surface that tile should see. A tile only ever sees what it's granted —
not the whole app.

---

## Testing your work

Tests drive the async interfaces with `asyncio.run` (no pytest-asyncio needed).
See [`tests/test_runtime_reference.py`](../tests/test_runtime_reference.py) for an
end-to-end activate → run example against real folders, and
[`tests/test_registry.py`](../tests/test_registry.py) for how to spin up a board
from fixtures.

```bash
pip install -e ".[dev]"
pytest
```

A good tile/connector PR includes a test proving it loads and runs.
