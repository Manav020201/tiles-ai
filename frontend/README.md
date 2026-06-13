# Tiles AI — board (frontend)

A simple React board for the Tiles AI control plane. Vite + React + TypeScript,
plain CSS, native `fetch` + `EventSource` — no state library, no UI framework, so
it stays inspectable.

## Run

Start the backend first (from the repo root):

```bash
# zero-setup demo: offline echo brain, no keys needed
PYTHONPATH=src TILES_ECHO=1 python -m tiles_ai.api      # http://127.0.0.1:8000
```

Then the board:

```bash
cd frontend
npm install
npm run dev                                             # http://localhost:5173
```

`vite.config.ts` proxies `/api` (including the SSE stream) to the backend.

## What it shows

- **Connect a brain** onboarding on first launch (cloud vs local, with a Test).
- A grid of tiles — tap to activate (green = running), each with a **permission
  tier** badge and a **resolved-brain** badge.
- **Run** a tile and see its result; draft-tier actions queue.
- An **Approvals** panel (approve/reject queued side effects) and a live
  **Activity** feed driven by `/api/events` (SSE).
- A per-tile **Brain** settings modal to pin a tile to a specific provider.

## Layout

```
src/
  api.ts              typed REST client
  types.ts            wire types (mirror tiles_ai/api/schemas.py)
  App.tsx             onboarding vs board; loads state; holds the SSE stream
  components/
    Onboarding.tsx    connect a brain (cloud/local + Test)
    TileCard.tsx      one tile: badges, activate/run, settings
    Approvals.tsx     pending approvals
    ActivityFeed.tsx  live event feed
    TileSettings.tsx  brain override
  styles.css
```
