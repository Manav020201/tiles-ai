"""Slack Catch-up — summarize a channel's recent activity. Read-only.

Input is a channel name or id. Lists channels to resolve a name to an id when
needed, reads recent history, and summarizes. Degrades gracefully on tool errors.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class SlackCatchup(Tile):
    async def run(self, input, context) -> ActionPlan:
        channel = str(input or "").strip().lstrip("#")
        if not channel:
            return ActionPlan(result="Enter a channel name or id.")

        history = await context.tools.call(
            "slack_get_channel_history", {"channel_id": channel, "limit": 50}
        )
        if not history.ok:
            return ActionPlan(result=f"Couldn't read #{channel}: {history.error}")

        summary = await context.model.complete(
            f"Catch me up on #{channel}:\n{history.output}",
            system=context.manifest.instructions,
        )
        return ActionPlan(result=summary)
