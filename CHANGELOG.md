# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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
