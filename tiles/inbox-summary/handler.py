"""Inbox Summary handler — the canonical read_only reference tile.

This is the file a new author copies. The whole tile is `run`: read through the
connector (allow-list enforced by `ctx.tools`), then ask the brain (`ctx.model`,
the global default since this tile pins no model) to summarize. It proposes no
actions and causes no side effects — true to its read_only tier.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class InboxSummary(Tile):
    async def run(self, input, context) -> ActionPlan:
        # Read through the connector. `ctx.tools.call` enforces the allow-list and
        # refuses side-effectful tools, so a read_only tile stays honest.
        messages = await context.tools.call("list_messages")

        prompt = (
            "Summarize these inbox messages in three short bullets:\n"
            f"{messages.output}"
        )
        summary = await context.model.complete(
            prompt, system=context.manifest.instructions
        )

        # No proposed actions: nothing to gate. The summary is the whole result.
        return ActionPlan(result=summary)
