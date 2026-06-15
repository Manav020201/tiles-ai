"""Inbox Summary (live) — read real Gmail and summarize it. Read-only.

Identical logic to the demo `inbox-summary` tile; the only difference is the
manifest binds it to the real `gmail-live` connector. The connector/tile split
means the handler doesn't change between mock and real.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class LiveInboxSummary(Tile):
    async def run(self, input, context) -> ActionPlan:
        messages = await context.tools.call("list_messages")
        prompt = (
            "Summarize these inbox messages in three short bullets:\n"
            f"{messages.output}"
        )
        summary = await context.model.complete(prompt, system=context.manifest.instructions)
        return ActionPlan(result=summary)
