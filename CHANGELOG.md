# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Real OAuth.** Connectors can declare an OAuth 2.0 authorization-code flow
  (`auth.oauth`); the board runs authorize → callback → token exchange and stores
  the access token in `oauth.local.yaml` (gitignored). The runtime injects it as
  the connector's bearer. `GET /api/connectors/{id}/oauth/start`,
  `GET /api/oauth/callback`, `POST /api/connectors/{id}/oauth/disconnect`; the
  connector edit form gains Authorize / Reauthorize / Revoke.
- **Scheduled triggers.** A tile can declare `schedule: { every: "5m" }` to run
  automatically on an interval. A `Scheduler` (wired into the API lifespan) reads
  the registry each tick and runs due tiles; `GET /api/schedules`; the create/edit
  forms have a "Run every" field and the tile sheet shows a ⏱ badge.
- **Multi-tile orchestration** (the `provides`/`consumes` seam). `Runtime.run_flow`
  runs tiles in sequence, piping each result into the next's input;
  `flow_candidates` matches `provides` ↔ `consumes`. `POST /api/flows/run` +
  `GET /api/tiles/{id}/flow`; the tile sheet shows a **Chain** section to run a
  tile, then feed it into a compatible one (e.g. Inbox Summary → Reply Drafter).
- **HTTP MCP transport.** `MCPConnector` now speaks the Streamable HTTP transport
  to remote/hosted MCP servers (an `http(s)://` endpoint), in addition to local
  stdio subprocesses. The first declared `auth.env` var is sent as a bearer token.
  Transport is chosen automatically by the endpoint.
- **Edit / disconnect an app from the board.** A ⚙ on each connector group opens
  a form to rename it, change its MCP command/env, re-fetch tools, or remove it
  (refused while tiles still use it). `update_connector` / `delete_connector`,
  `PUT`/`DELETE /api/connectors/{id}`. Tiles can be deleted too (`DELETE /api/tiles/{id}`).
- **Per-tile activity** in the tile sheet — its recent events (activated, ran,
  queued, …) filtered from the live stream.
- A README hero illustration.
- **Model settings in the UI.** A 🧠 nav-bar button opens a "Brains" panel to add
  a cloud LLM or a local (Ollama) model, set the default, test it, or remove it
  (`DELETE /api/providers/{id}`) — any time, not just first-launch onboarding.
- **Edit a tile from the board.** The tile sheet's "Edit tile" opens a form for
  its manifest fields (name/icon/description/instructions/tier/input); the handler
  stays in code. `scaffold.update_tile` + `PUT /api/tiles/{id}`.
- **Hot reload.** `tiles up --reload` re-discovers on changes to `*.py` and
  `*.yaml` under the board (WatchFiles), via an import-string app factory.
- **Connect an app from the board.** A "🔌 New app" form takes an MCP server
  command, **introspects its tools live** (`POST /api/connectors/introspect` →
  `MCPConnector` → `live_tools`), and scaffolds the connector — which is then
  available to bind tiles to. `scaffold_connector` + `POST /api/connectors`.
- **Errors surfaced on the board.** An "Issues" panel shows tiles/connectors
  that failed to load and why (`GET /api/errors`); a **⟳ rescan** button
  (`POST /api/reload`) re-discovers from disk after you edit files.
- **Create tiles from the board.** A "＋ New tile" form scaffolds a tile
  (manifest + handler) from the UI; the registry re-scans and the tile appears
  live — no restart. Backed by a shared `tiles_ai.scaffold` module (also behind
  `tiles new`), `Registry.rescan`, and `GET /api/connectors` + `POST /api/tiles`.
- **Local "smart PC" pack** (zero credentials): the local-files connector gains
  `find_files` + `move_file`, and three tiles — Summarize Folder, Find Files
  (read_only), and Tidy Folder (draft: proposes sorting files into type folders,
  each move queued for your approval). The first *local* side-effect flow, tested
  end to end (propose → approve → files move on disk).

## [0.1.1] - 2026-06-15

### Fixed
- **First run no longer shows an empty board.** A fresh `pip install tiles-ai`
  followed by `tiles up` in an empty directory previously discovered zero tiles
  (the starter `tiles/`/`connectors/` were not bundled). The package now ships a
  **starter board** (`tiles_ai/starter_board/`, generated at release-build time
  by `scripts/bundle_starter.py`).

### Added
- **`tiles init`** seeds the starter board into the current folder (`--root`,
  `--force`). `tiles up` auto-seeds when it finds no board, so the very first
  command always opens a populated, editable board.

## [0.1.0] - 2026-06-14

First public release.

### Added
- **`tiles` CLI**: `tiles up` (run API + board, `--echo` for an offline demo
  brain), `tiles list`, `tiles new <id>` (scaffold a tile).
- **CI** (GitHub Actions): backend lint (ruff) + tests on Python 3.11/3.12, and
  frontend tests (Vitest) + type-check + build. **Release** workflow publishes to
  PyPI on a `v*` tag via Trusted Publishing, bundling the built board into the wheel.
- **Frontend tests** (Vitest + Testing Library): grouping/result helpers, the API
  client, and the TileIcon component.
- FastAPI serves the built board at `/` (dev build or the packaged board), so the
  whole app runs on one port.
- Real **MCP-backed connector** (`MCPConnector`, stdio JSON-RPC) + an example
  server; a `local-files` connector and an `Ask My Files` tile.
- Credential **auth hook**: connectors declare required env vars; the board shows
  "needs token" and blocks activation until they're set.
- **App packs**: GitHub (triage, comment), Slack (catch-up, drafter), and Web
  Search / Research (Brave) tiles. Pack handlers are unit-tested against fake
  tool/model contexts (arg construction, propose→gate flow, degradation).
- **Instant tiles**: Ask, Summarize, Translate, Extract, Brainstorm.
- iOS-style board: graphite-glass app icons, a bottom sheet to run tiles, live
  activity feed, approvals, and a brain picker; light + dark.

### Notes
- The GitHub/Slack tool surfaces follow the official MCP servers and may need
  adjustment against your server version (see each connector's README).

## [0.0.1]
- Initial contract, registry, runtime, permission gate, model adapter, FastAPI
  control plane, and React board. MIT licensed.
