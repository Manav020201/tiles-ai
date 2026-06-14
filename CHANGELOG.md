# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
