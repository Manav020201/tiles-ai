"""Slack Drafter — draft a message and propose posting it.

Input: "#channel: what to say". Reads recent channel context, drafts a message
with the brain, then PROPOSES slack_post_message (side_effect=True). Under the
draft tier the gate queues it for approval — nothing posts on its own.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, ProposedAction, Tile


class SlackDrafter(Tile):
    async def run(self, input, context) -> ActionPlan:
        ref, _, intent = str(input or "").partition(":")
        channel = ref.strip().lstrip("#")
        if not channel:
            return ActionPlan(result="Enter a target as '#channel: your intent'.")

        history = await context.tools.call(
            "slack_get_channel_history", {"channel_id": channel, "limit": 20}
        )
        context_text = history.output if history.ok else "(no recent context)"

        body = await context.model.complete(
            f"Intent: {intent.strip() or 'a short update'}\nRecent context:\n{context_text}",
            system=context.manifest.instructions,
        )

        propose = ProposedAction(
            tool="slack_post_message",
            args={"channel_id": channel, "text": body},
            side_effect=True,
            summary=f"Post to #{channel}",
        )
        return ActionPlan(result={"draft": body, "channel": channel}, actions=[propose])
