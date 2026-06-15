"""Reply Drafter (live) — draft a reply to a real email, queue it for approval.

Identical logic to the demo `reply-drafter`; bound to the real `gmail-live`
connector. It reads the inbox, drafts a reply with the brain, and returns a
*proposed* send — the permission gate queues it (draft tier) until you approve.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, ProposedAction, Tile


class LiveReplyDrafter(Tile):
    async def run(self, input, context) -> ActionPlan:
        messages = await context.tools.call("list_messages")
        inbox = messages.output or []

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

        send = ProposedAction(
            tool="send_message",
            args={"to": target.get("from", "unknown@example.com"), "body": body},
            side_effect=True,
            summary=f"Reply to {target.get('from', 'unknown')}",
        )
        return ActionPlan(result={"draft": body, "to": send.args["to"]}, actions=[send])
