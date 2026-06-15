"""Reply Drafter handler — the canonical draft-tier reference tile.

Shows the propose -> gate flow: read through the connector, draft a reply with
the brain, then return a *proposed* `send_message` action flagged
`side_effect=True`. The handler never sends anything — under the `draft` tier the
permission gate queues the action for human approval. Approve it and the runtime
executes the send through the connector; reject it and nothing happens.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, ProposedAction, Tile


class ReplyDrafter(Tile):
    async def run(self, input, context) -> ActionPlan:
        # Read the inbox (allow-listed, non-side-effectful).
        messages = await context.tools.call("list_messages")
        inbox = messages.output or []

        # Pick the message to reply to. `input` may be a message dict (direct use)
        # or text — e.g. a summary piped from another tile via the flow API
        # (consumes: email.summary). Either way, fall back to the first unread.
        if isinstance(input, dict):
            target = input
            context_note = ""
        else:
            target = next((m for m in inbox if m.get("unread")), inbox[0] if inbox else {})
            context_note = f"\n\nUse this context: {input}" if input else ""

        body = await context.model.complete(
            f"Draft a short reply to this email: {target}{context_note}",
            system=context.manifest.instructions,
        )

        # Propose the send. side_effect=True routes it through the gate; under the
        # draft tier it queues for approval instead of firing.
        send = ProposedAction(
            tool="send_message",
            args={"to": target.get("from", "unknown@example.com"), "body": body},
            side_effect=True,
            summary=f"Reply to {target.get('from', 'unknown')}",
        )
        return ActionPlan(result={"draft": body, "to": send.args["to"]}, actions=[send])
