# 🟩 Tiles AI

**A home screen for your AI agents.** Lay your agents out as tiles on a board,
tap one to run it, and stay in control of anything it does.

[![PyPI](https://img.shields.io/pypi/v/tiles-ai.svg)](https://pypi.org/project/tiles-ai/)
[![CI](https://github.com/Manav020201/tiles-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Manav020201/tiles-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

![Tiles AI — a home screen for your AI agents](docs/hero.svg)

## What is it?

Think of your phone's home screen — but every app is an AI agent.

- A **board** is a grid of **tiles**.
- Each **tile** is one agent that does a single job — *"summarize my inbox"*,
  *"tidy this folder"*, *"draft a reply"*.
- Tap a tile and it turns **green** — running.

Tiles AI handles the parts *around* an agent — running it, watching it, asking
your permission before it acts, and connecting it to your apps. You bring the
agent's logic (plain Python, or wrap LangChain / CrewAI / the OpenAI SDK).

It's built for **developers learning to build agents**: start from a ready-made
board and add your own tiles right from the screen.

## Quick start

You'll need **Python 3.11+**. The board ships pre-built in the package:

```bash
pipx install tiles-ai      # or: pip install tiles-ai
tiles up --echo            # seeds a starter board here on first run
```

Open **http://127.0.0.1:8000** — you'll see a starter board running on a free
offline brain (no API key needed). The first run drops the starter tiles and
connectors into the current folder (so you can edit them); run `tiles init`
yourself to seed a board without starting the server. When you're ready for a
real model, run `tiles up` and connect a brain from the screen.

<details>
<summary>From source (to hack on Tiles itself)</summary>

You'll also need **Node 18+** to build the board once.

```bash
git clone https://github.com/Manav020201/tiles-ai && cd tiles-ai
pip install -e ".[dev]"
npm --prefix frontend install && npm --prefix frontend run build
tiles up --echo
```
</details>

## What you can do

**Right away — no API keys:**

- **Instant tiles** — Ask, Summarize, Translate, Extract, Brainstorm.
- **Your files** — summarize a folder, find files, or tidy a folder (it *proposes*
  the moves; you approve them).

**Add your apps** — GitHub, Slack, web search, Gmail, and anything with an
[MCP](https://modelcontextprotocol.io) server (local or remote), via an API token
or OAuth.

**All from the board — no editor required:**

| | |
|---|---|
| ➕ **Create a tile** | fill a form; Tiles writes the files for you |
| 🔌 **Connect an app** | paste its command; Tiles reads its tools automatically |
| 🧠 **Choose your model** | cloud (Anthropic / OpenAI) or local (Ollama) |
| ✅ **Approve before it acts** | anything that writes or sends waits for your OK |
| ⏱ **Schedule & chain** | run a tile on a timer, or feed one tile's output into another |
| 👀 **Observe** | live activity per tile, and clear errors as you go |

## How it works

Three ideas:

| Concept | What it is |
|---|---|
| **Tile** | an agent — a model + instructions + a permission level. The thing you tap. |
| **Connector** | a reusable connection to one app (e.g. GitHub). Many tiles can share it. |
| **Brain** | the model that powers tiles. Set one once; a tile can pin its own. |

**Permissions are built in.** Every tile has a level: **read-only** (never acts),
**draft** (proposes actions you approve), or **autonomous**. Green means
*running*, not *unsupervised*.

<details>
<summary>Architecture (for the curious)</summary>

```
React board ──HTTP/SSE──▶ FastAPI ──▶ runtime ──▶ permission gate ──▶ connector ──▶ app
                                         └──▶ model adapter ──▶ brain (cloud / local)
```

Connectors talk to apps over [MCP](https://modelcontextprotocol.io) (stdio or
HTTP). The full design is in [SPEC.md](SPEC.md).
</details>

## Make your own tile

The easy way: click **➕ New tile** on the board, fill the form, and open the
generated `handler.py` to customize.

In code, a tile is a small folder with a manifest and one method:

```python
from tiles_ai.contracts import ActionPlan, Tile

class MyTile(Tile):
    async def run(self, input, context) -> ActionPlan:
        answer = await context.model.complete(str(input))
        return ActionPlan(result=answer)
```

Full guide, including how to connect a new app: **[docs/AUTHORING.md](docs/AUTHORING.md)**.

## Docs

- **[SPEC.md](SPEC.md)** — the design and the tile contract
- **[docs/AUTHORING.md](docs/AUTHORING.md)** — build a tile or a connector
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — dev setup and how to help
- **[CHANGELOG.md](CHANGELOG.md)** — what's new

## Status

Active development; well-tested with CI on Python 3.11 and 3.12.

**Already here:** tiles **chain** (sequential flows), run on an **interval
schedule**, and connect via **OAuth** (authorization-code) or API keys.

**Refinements still to come:** branching / fan-out flows (only linear chains
today) · cron and event triggers (only intervals today) · automatic OAuth token
refresh. Out of scope for now: hosting and multi-user.

## License

[MIT](LICENSE).
