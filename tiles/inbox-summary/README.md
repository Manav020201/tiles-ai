# Inbox Summary

A **read_only** reference tile. Reads your inbox through the Gmail connector and
returns a three-bullet summary. It never sends or changes anything.

## What it demonstrates

- **Default-brain fallback.** The manifest pins no `model`, so the tile uses
  your global default brain. Connect one brain and this tile just works.
- **Allow-listed reads.** It grants only `list_messages`. `ctx.tools.call`
  enforces that allow-list and refuses side-effectful tools — a read_only tile
  cannot touch the world even by mistake.
- **No proposed actions.** `run` returns just a result, so nothing reaches the
  permission gate.

## Configure

Nothing to configure for the v0 mock — the Gmail connector returns a small fake
inbox. To point it at real mail, swap `connectors/gmail` for a real
MCP-backed connector; this tile is unchanged.

## Copy it

1. Copy this folder to `tiles/<your-id>/`.
2. Edit `manifest.yaml` (`id`, `name`, `connector`, `allowed_tools`, `instructions`).
3. Implement `run` in `handler.py`.
