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

You'll need **Python 3.11+**. The board ships pre-built in the package.

**macOS / Linux:**

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
<summary><strong>🪟 Windows — step-by-step (start here if you're new)</strong></summary>

Do these in order. Commands are for **PowerShell** (Start menu → type
"PowerShell" → Enter).

**1. Install Python 3.11 or newer**
- Get it from [python.org/downloads/windows](https://www.python.org/downloads/windows/)
  (or the Microsoft Store).
- On the **first installer screen, tick “Add python.exe to PATH”**, then click
  Install. (This one checkbox saves a lot of pain.)
- Check it worked — in a *new* PowerShell window:
  ```powershell
  python --version
  ```
  You should see `Python 3.11.x` (or higher).

**2. Install Tiles into its own folder (a “virtual environment”)**
This keeps Tiles separate from the rest of your system.
```powershell
python -m venv $HOME\tiles-env
$HOME\tiles-env\Scripts\pip install --upgrade pip tiles-ai
```

**3. Run it**
```powershell
mkdir $HOME\tiles-demo; cd $HOME\tiles-demo
$HOME\tiles-env\Scripts\tiles up --echo
```
Now open **http://127.0.0.1:8000** in your browser. Press **Ctrl + C** in
PowerShell to stop it.

**4. Switch to a real model**
Stop it (Ctrl + C), then run **without** `--echo`:
```powershell
$HOME\tiles-env\Scripts\tiles up
```
On the board click **Settings (🧠)** and paste your API key (Anthropic or
OpenAI). It’s saved on your machine and used for every tile.

**Tip — type `tiles` instead of the full path.** “Activate” the environment first:
```powershell
$HOME\tiles-env\Scripts\Activate.ps1
tiles up
```
If PowerShell says running scripts is disabled, run this once, then try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
(Prefer the old Command Prompt? Use `tiles-env\Scripts\activate.bat` instead.)

**Two Windows-specific gotchas**
- **The “Local files” tiles** (Summarize Folder, Ask My Files, …) launch a helper
  with `python3`, which Windows usually calls just `python`. Fix it once on the
  board: 🔌 **local-files → ⚙**, and in the **MCP server command** change
  `python3` to `python`. Point it at a Windows path, e.g.
  `python examples\mcp_servers\files_server.py C:\Users\You\Documents`.
- **Connector API keys** (like a Brave key): easiest is to paste them right on the
  board (tap the tile → paste). If you’d rather use the terminal, in PowerShell
  it’s `$env:BRAVE_API_KEY="your-key"` *before* `tiles up` (not `export`).
</details>

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
[MCP](https://modelcontextprotocol.io) server (local or remote). Paste any API
key the app needs **right in the board** (stored locally in `secrets.local.yaml`,
gitignored), or connect via OAuth.

**All from the board — no editor required:**

| | |
|---|---|
| ➕ **Create a tile** | fill a form; Tiles writes the files for you |
| 🔌 **Connect an app** | paste its command; Tiles reads its tools automatically |
| 🧠 **Choose your model** | cloud (Anthropic / OpenAI) or local (Ollama) |
| ✅ **Approve before it acts** | anything that writes or sends waits for your OK |
| ⏱ **Schedule & chain** | run a tile on a timer, or feed one tile's output into another |
| 👀 **Observe** | live activity per tile, a 🔥 **token-usage** counter, and clear errors as you go |

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

## Using the board — a complete guide

### Reading the board

Tiles are grouped by the app they use (**Instant**, **Local-files**, **Gmail**,
**Web-search**, …). Each icon tells you its state at a glance:

- **Green icon** — the tile is *active* (running / listening).
- **🔒 lock badge** — the tile needs something before it can run (usually an API
  key); tap it to add one.
- The top bar has **🧠** (choose your model), **⟳** (rescan after editing files),
  and an **Issues** panel if any tile failed to load.

Tap any tile to open its **sheet** — that's where everything happens.

### The basic loop (every tile works this way)

1. **Tap** the tile → its sheet slides up.
2. **Toggle "Running"** on (the icon turns green). "Green = running, not
   unsupervised."
3. If the tile takes input, a box appears — **type your input** (some are
   optional; the box says so).
4. Press **Run**. The result shows under **Last run**.
5. For **draft** tiles, anything that writes/sends is **not** done immediately —
   it's queued for your approval (see [Approvals](#approvals-draft-tiles)).

A tile's badges show its **permission tier** (`read only` / `draft` /
`autonomous`) and which **brain** it uses.

### The tile catalog

What every starter tile does, what to type, and what it needs.

**Instant — work immediately, only need a model (no app, no keys):**

| Tile | What to type |
|---|---|
| **Ask** | any question |
| **Summarize** | text to condense |
| **Translate** | text — optionally prefix `to spanish:` to pick a language |
| **Extract** | messy text → pulls out people, dates, tasks, links |
| **Brainstorm** | a topic or problem to riff on |

**Local files — read/organize a folder. No API key, no Node (a bundled Python
server):**

| Tile | Tier | What to type |
|---|---|---|
| **Ask My Files** | read only | a question about your documents |
| **Find Files** | read only | a filename or keyword |
| **Summarize Folder** | read only | *(optional)* a subfolder — blank = the whole folder |
| **Tidy Folder** | draft | *(optional)* a folder — it **proposes** moving files into type subfolders; you approve each move |

> These read the folder the **local-files** connector points at (the bundled
> `sample_docs/` by default). To use your own folder: 🔌 `local-files` → ⚙ →
> change the last argument of the MCP command to your folder's path.

**Gmail — works two ways:**

| Tile | Tier | What to type |
|---|---|---|
| **Inbox Summary** / **Reply Drafter** | read only / draft | the **mock** — fake data, zero setup, for learning the flow |
| **Inbox Summary (live)** / **Reply Drafter (live)** | read only / draft | your **real** Gmail via Google OAuth — see [docs/GMAIL.md](docs/GMAIL.md) |

> Real Gmail needs a one-time Google Cloud OAuth app (Google's requirement). After
> that you connect it entirely from the board: 🔌 **Gmail (live)** → ⚙ → paste the
> client ID + secret → **Authorize**. Full walkthrough: **[docs/GMAIL.md](docs/GMAIL.md)**.

**Web search — needs a free [Brave API key](https://brave.com/search/api) + Node:**

| Tile | What to type |
|---|---|
| **Web Search** | what to search for |
| **Research** | a question — answered with web sources |

**GitHub — needs a `GITHUB_PERSONAL_ACCESS_TOKEN` + Node:**

| Tile | Tier | What to type |
|---|---|---|
| **GitHub Triage** | read only | `owner/repo` (e.g. `octocat/hello-world`) |
| **GitHub Comment** | draft | `owner/repo#issue: what to say` — drafted, queued |

**Slack — needs `SLACK_BOT_TOKEN` + `SLACK_TEAM_ID` + Node:**

| Tile | Tier | What to type |
|---|---|---|
| **What did I miss** | read only | a channel name or id |
| **Message Drafter** | draft | `#channel: what to say` — drafted, queued |

> Tiles needing a key show 🔒 until you add one. Tap the tile and paste the key
> right there (or 🔌 → ⚙ → **API keys**). Keys are saved to `secrets.local.yaml`
> (gitignored) and never leave your machine. The GitHub/Slack/Web-search apps run
> via `npx`, so they need **Node 18+** installed.

### Approvals (draft tiles)

A `draft` tile never writes to the outside world on its own. When it wants to
(send an email, comment on an issue, move a file), it **proposes** the action and
it lands in the **Approvals** queue. You review the exact action and **Approve**
or **Reject** — nothing happens until you do. This is the core safety guarantee.

### Schedule & chain

- **Schedule** — give a tile a `Run every` interval (e.g. `15m`) in its New/Edit
  form and it runs on a timer; the sheet shows a ⏱ badge.
- **Chain** — in a tile's sheet, the **Chain** section offers compatible tiles to
  pipe into. Run one, then feed its output straight into another (e.g. *Inbox
  Summary → Reply Drafter*).

### Choosing your model (🧠)

Click **🧠** in the top bar to open **Brains**. Add a **cloud** model (Anthropic
or OpenAI — paste your API key) or a **local** one (Ollama), set a **default**,
and **Test** it. Every tile uses the default unless it pins its own. Keys are
saved in `brain.local.yaml` (gitignored). *(Running with `tiles up --echo` forces
an offline demo brain and ignores real keys — use plain `tiles up` for real
models.)*

---

## Create a tile (from the board)

1. Click **➕ New tile**.
2. Fill the form:
   - **Name** + **icon** + one-line **description**.
   - **Instructions** — the agent's system prompt ("You summarize… cite the
     source… if unknown, say so").
   - **Permission tier** — `read only` (never writes), `draft` (proposes, you
     approve), or `autonomous`.
   - **App** *(optional)* — bind to a connector and pick which of its tools the
     tile may use. Leave blank for an **instant** tile (model only).
   - **Input** / **Run every** *(optional)*.
3. **Create** — Tiles scaffolds `tiles/<id>/` (manifest + handler + README) and
   the tile appears on the board immediately.
4. **Go deeper:** open `tiles/<id>/handler.py` and edit `run`. A tile is a small
   folder with a manifest and one method:

   ```python
   from tiles_ai.contracts import ActionPlan, Tile

   class MyTile(Tile):
       async def run(self, input, context) -> ActionPlan:
           answer = await context.model.complete(str(input))
           return ActionPlan(result=answer)
   ```

   `context.tools.call(...)` reads through your connector (allow-listed,
   read-only); to write, return a `ProposedAction` and the gate handles approval.
   Full field-by-field reference: **[docs/AUTHORING.md](docs/AUTHORING.md)**.

## Connect a new app (from the board)

For any app with an [MCP](https://modelcontextprotocol.io) server (local or
remote):

1. Click **🔌 New app**.
2. Paste the **MCP server command** (e.g.
   `npx -y @modelcontextprotocol/server-github`) — or an `http(s)://` URL for a
   remote server — and the names of any **env vars** it needs (e.g.
   `GITHUB_PERSONAL_ACCESS_TOKEN`).
3. Click **Fetch tools** — Tiles launches the server and reads its tool surface.
   Each tool has a **"writes"** checkbox: leave it checked for tools that change
   the world (send, post, delete) and unchecked for reads. *This flag is
   safety-critical — the permission gate trusts it.*
4. **Save** — the connector is scaffolded and now appears in the New Tile form's
   app picker.
5. **Add its key** — open the connector (🔌 → ⚙ → **API keys**) and paste the
   value, or paste it from any tile that shows 🔒. For OAuth apps, use
   **Authorize** instead. Edit or remove a connector anytime from the same ⚙.

## Troubleshooting

<details>
<summary><strong>The board is empty, or <code>http://127.0.0.1:8000</code> shows <code>404 Not Found</code></strong></summary>

You're almost certainly running a **source checkout** or an **editable install**
(`pip install -e`) instead of the published package. The board UI and the starter
tiles are built into the *wheel*; a source tree only has them after a release
build, so it serves nothing at `/` and shows no tiles.

The fix is to install the real package into an **isolated environment** so nothing
shadows it (see the next item). If you *do* want a checkout to serve the board:

```bash
npm --prefix frontend run build && cp -r frontend/dist src/tiles_ai/web
python scripts/bundle_starter.py        # adds the seedable starter board
```
</details>

<details>
<summary><strong><code>pip install tiles-ai</code> says "Requirement already satisfied" / won't update</strong></summary>

A pre-existing install — often an editable one from a clone — is registered, so
`import tiles_ai` resolves to *that*, not the download. Install into a fresh
virtual environment instead (non-destructive; leaves any dev checkout intact):

```bash
python3 -m venv ~/tiles-test-env
~/tiles-test-env/bin/pip install --upgrade pip tiles-ai
mkdir -p ~/tiles-demo && cd ~/tiles-demo
~/tiles-test-env/bin/tiles up --echo
```

Or, to use your base environment, remove the old install first:
`pip uninstall tiles-ai` then `pip install tiles-ai` (re-run
`pip install -e ".[dev]"` in your clone afterwards if you were developing).
</details>

<details>
<summary><strong><code>pipx install tiles-ai</code> fails with an <code>ensurepip</code> / venv error</strong></summary>

This is a pipx + Python toolchain problem (commonly a freshly-installed Python
whose `ensurepip` is broken), not a Tiles problem — pipx never reaches the
package. Either point pipx at a known-good Python:

```bash
PIPX_DEFAULT_PYTHON=$(which python3) pipx install tiles-ai
```

or skip pipx and use the plain `venv + pip` recipe in the item above.
</details>

<details>
<summary><strong>I added a real API key and Test passed, but tiles still just echo</strong></summary>

You're running `tiles up --echo`. The `--echo` flag forces an **offline demo
brain** — every tile (and the Test button) returns a canned echo, and real keys
are ignored by design. Restart **without** `--echo`:

```bash
tiles up
```

then add your key in **Settings (🧠)**. It's saved to `brain.local.yaml` and used
for every tile. (On recent versions, clicking Test while in `--echo` mode says so
explicitly instead of reporting a false "working".)
</details>

<details>
<summary><strong>A tile fails with "model call failed" / HTTP 529 / 502</strong></summary>

`529 Overloaded` (and `429`, `503`) are **transient errors from the model
provider**, not a Tiles bug — your key is working, the provider is just busy.
Tiles retries these automatically with backoff; if it still fails, wait a few
seconds and run the tile again. A persistent `401`/`403` instead means a bad or
unauthorized API key — re-check it in **Settings (🧠)**.
</details>

<details>
<summary><strong>I have an old version installed</strong></summary>

Check with `tiles --version` and `pip show tiles-ai`. Upgrade with
`pip install --upgrade tiles-ai` (inside the right environment — see above).
</details>

## Docs

- **[SPEC.md](SPEC.md)** — the design and the tile contract
- **[docs/AUTHORING.md](docs/AUTHORING.md)** — build a tile or a connector
- **[docs/GMAIL.md](docs/GMAIL.md)** — connect your real Gmail (Google OAuth)
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
