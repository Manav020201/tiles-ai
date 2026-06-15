# Handoff — Tiles AI

Working notes for anyone (human or a fresh AI session) continuing this project.
Authoritative specs live in [`SPEC.md`](SPEC.md); this file is the practical map.

## What this is

**Tiles AI** — a phone-home-screen control plane for AI agents. A *board* is a
grid of *tiles*; each tile is an agent you tap to run (green = running). The
project's value is the layer agent frameworks are weak at: **register → activate
→ observe → permission → (later) compose**. A tile can wrap any agent logic; we
don't compete on writing it.

**Audience & goal:** *new developers learning agent engineering.* The board is
the teaching visualization. The north star is that authoring a tile (and
connecting an app) is so easy a beginner learns by doing — and they can do
*everything from the board UI* (create/edit/delete tiles & connectors, manage
brains, run, approve, observe), then drop into the generated files to go deeper.
API keys are fine; frictionless authoring is the priority.

## Repo & deploy

- GitHub: **https://github.com/Manav020201/tiles-ai** (public, `main`).
- PyPI: **`tiles-ai` v0.1.0 published** (https://pypi.org/project/tiles-ai/) via
  Trusted Publishing (OIDC, `pypi` GitHub environment) — `pipx install tiles-ai`.
  Release is tag-driven (`.github/workflows/release.yml`, on `v*`); the wheel
  bundles the pre-built board. Next release: bump `version` in `pyproject.toml`,
  tag `vX.Y.Z`, push. See [`RELEASING.md`](RELEASING.md).
- Owner email: manavsinghai11@gmail.com. Author in pyproject: "Manav Singhai".
- Push needs a PAT with the **`workflow`** scope (creating `.github/workflows`).

## How to run / test / lint

```bash
pip install -e ".[dev]"            # backend + dev deps (pytest, httpx, ruff)
TILES_ECHO=1 python -m tiles_ai.api   # API+board on :8000 (offline echo brain)
# or: tiles up --echo   /   tiles up --reload   /   tiles list   /   tiles new <id>

cd frontend && npm install
npm run dev      # board on :5173 (vite proxies /api -> :8000)
npm run build    # tsc + vite (CI gate); npm run test (vitest)
```

CI gates (must stay green — `.github/workflows/ci.yml`):
- `ruff check src tests` && `ruff format --check src tests`
- `pytest` (backend, Python 3.11 & 3.12)
- frontend `npm run test` + `npm run build`

Current counts: **165 backend + 15 frontend tests**. Run `pytest -q` and
`npm --prefix frontend run test`.

## Architecture & layout

```
React board ──HTTP/SSE──▶ FastAPI control plane
  registry ──▶ runtime ──▶ permission gate ──▶ connector ──▶ app (mock | MCP stdio/HTTP)
                 │                                  ▲
                 ▼                                  │
           model adapter ──▶ brain (Anthropic/OpenAI/Ollama/echo)
```

```
src/tiles_ai/
  contracts/    THE SPINE — pydantic schemas, interfaces, lifecycle, permissions,
                brain resolution, cross-manifest validation. Read SPEC.md first.
  registry/     discover + validate connectors/ and tiles/; load adapter/handler
                classes; Registry.rescan() re-discovers in place (live add/edit).
  connectors/   mock.py (MockConnector), mcp.py (MCPConnector + StdioMCPClient +
                StreamableHttpMCPClient + introspect()).
  model/        BrainStore (provider config + default, YAML), ModelAdapter
                (resolve brain, complete, test), clients (Echo/Ollama/Anthropic/OpenAI).
  runtime/      Runtime (activate/run/deactivate, brain override), gate.py
                (PermissionGate + approval queue), handles.py (ctx.tools, ctx.model).
  events/       in-process EventBus (SSE source).
  api/          app.py (create_app + all REST/SSE endpoints), factory.py
                (make_app for `uvicorn --reload`), schemas.py, __main__.py.
  scaffold.py   build/validate/write/update/delete tiles & connectors (shared by
                `tiles new` CLI and the board's create/edit endpoints).
  handlers.py   PromptTile (instant-tile base: input -> brain -> result).
  cli.py        `tiles` console script (up/list/new).
connectors/     authored connectors: gmail (mock), local-files (mcp stdio),
                github/slack/web-search (mcp, bring-your-own-token).
tiles/          authored tiles (17): instant (ask/summarize/translate/extract/
                brainstorm), gmail (inbox-summary/reply-drafter), local-files
                (ask-my-files/summarize-folder/find-files/tidy-folder), github
                (github-triage/github-comment), slack (slack-catchup/slack-drafter),
                web-search (web-search/research).
examples/mcp_servers/files_server.py   dependency-free stdio MCP server (test
                fixture AND the local-files backend). Tools: list_dir, read_file,
                find_files, move_file, whoami.
frontend/src/   React board. App.tsx (state + SSE + layout), components/
                (TileIcon, TileSheet, NewTileForm, AddConnectorForm,
                EditTileForm, EditConnectorForm, Settings, Issues, Approvals,
                ActivityFeed, Onboarding), api.ts, types.ts, lib/ (pure helpers).
tests/          contract + integration + handler + http + scaffold/api tests.
docs/           AUTHORING.md, hero.svg.
```

## Core concepts (the contract)

- **Connector** = durable connection to one app (auth + tool surface). One per
  app, shared by many tiles. `kind: mock | mcp | custom`. For `mcp`, `endpoint`
  is a stdio launch command OR an `http(s)://` URL (Streamable HTTP). The
  manifest's `tools` (with `side_effect` flags) are the AUTHORITY the gate trusts;
  the live server only executes.
- **Tile** = agent: model + instructions + permission tier, optionally bound to
  one connector + allow-listed to a subset of its tools. Optional `connector`
  (omit = "instant" tile, brain only). Optional `model` pin (omit = global
  default brain). Declares `provides`/`consumes` (Capability objects) — the
  **composition seam, currently declared but only minimally wired** (see roadmap).
- **Permission tiers** (`permissions.evaluate` is the single policy):
  read_only → side effect REJECTED; draft → QUEUED for approval; autonomous →
  EXECUTED. A non-side-effect action always executes.
- **The gate is the only path to a side effect.** RunContext gives a handler
  only `ctx.tools` (allow-listed, non-side-effect reads) and `ctx.model`; it has
  NO raw connector. Side effects must be *proposed* via `ActionPlan.actions`.
- **Brain** = one global provider config (hosted or local/Ollama) + a default;
  a tile uses the default unless it pins/overrides. `resolve_brain` order:
  UI override → tile pin → global default. Keys live only in `brain.local.yaml`
  (gitignored), never in manifests.
- **Lifecycle:** defined → available → active → (paused/stopped); `composed`
  reserved for orchestration.

## Important conventions & gotchas

- **Async** everywhere in connector/tile/runtime interfaces. Tests drive async
  with `asyncio.run` (no pytest-asyncio).
- **Pydantic v2**; `extra="forbid"` on manifests; validate before writing.
- **Tests that CREATE tiles/connectors MUST use a temp board** (`tmp_path`),
  never `REPO_ROOT` — else they pollute the repo. See `_tmp_client` in
  `tests/test_api.py`. After any create/edit test, the repo must stay clean.
- **Live verification pattern:** copy connectors/tiles/examples/sample_docs into
  `/tmp/tiles-demo-board`, run `TILES_ECHO=1 TILES_ROOT=$DEMO python -m tiles_ai.api`,
  drive the board via the Claude Preview MCP tools (preview_start "board" uses
  `.claude/launch.json`). Tear down + `rm -rf` the temp board after.
- **Disk:** the dev machine has run critically low (~1-3 GB free). `node_modules`
  is the big disposable. Avoid unnecessary reinstalls.
- **`watchfiles`** is a dependency so `tiles up --reload` watches `*.yaml` too.
- **ruff** auto-reorders imports/format — run `ruff check --fix && ruff format`
  after edits; it will modify files (re-Read before editing them again).
- Board create/edit forms and the CLI both go through `scaffold.py`, so they
  can't drift.

## Additive contract changes already made (beyond original SPEC)

- `Connector.from_manifest` factory; `RunContext.tools`/`.model` handles (raw
  connector removed for safety).
- `AuthConfig.env` (env var names a connector needs → bearer/passthrough);
  `AuthConfig.oauth` (`OAuthConfig`) for the OAuth flow.
- `ModelRef`/brain override resolution; `register_hosted_client`.
- `RunContext` carries no secrets.
- `Schedule` + `TileManifest.schedule` (interval triggers).
- `Runtime`: `token_store` param (injects OAuth bearer); `run_flow`,
  `flow_candidates`, `run_scheduled`. `Scheduler`. `MCPConnector.access_token`.

## What's built (high level)

Full stack: contract, registry, runtime + gate + approval queue, model adapter
(4 clients), events/SSE, FastAPI API, iOS-style React board. Real MCP connector
(stdio + HTTP). App packs (gmail mock, github/slack/web-search, local-files).
Instant tiles. `tiles` CLI (+ `--reload`). Board is full-CRUD: create/edit/delete
tiles & connectors from the UI, connect apps by MCP command (with live tool
introspection), manage brains (cloud/Ollama), per-tile activity, error surfacing,
rescan. PyPI packaging + CI + release workflow. MIT licensed.

## Roadmap

Done (this session): ✅ multi-tile orchestration (sequential flows:
`Runtime.run_flow`, `flow_candidates`, `/api/flows/run`, tile-sheet Chain) · ✅
scheduled triggers (interval `schedule`, `Scheduler` in the API lifespan,
`/api/schedules`) · ✅ real OAuth (`auth.oauth`, `tiles_ai/oauth.py` TokenStore +
flow, `/api/connectors/{id}/oauth/*`, runtime injects the bearer).

Remaining: branching/fan-out flows (only sequential ships) · cron & event
triggers (only interval ships) · OAuth refresh-token rotation · multi-user /
hosting / marketplace (deliberate non-goals).

## Honest gaps

- GitHub/Slack/Web-Search pack tool names follow the official MCP servers but
  were NOT live-verified against a running server (no tokens here). Handlers are
  unit-tested against fakes; arg shapes may need adjustment per server version.
- No real demo GIF (can't screen-record from the build env); README has an SVG
  hero + a recipe (`tiles up --echo` + a screen recorder).
- Frontend tests cover helpers/api/TileIcon; no full App e2e.
