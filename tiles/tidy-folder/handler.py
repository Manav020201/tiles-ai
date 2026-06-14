"""Tidy Folder — propose sorting a folder's files into type-named subfolders.

The first *local* draft-tier tile. It reads the listing and proposes a move_file
action per file (side_effect=True), grouping by extension. Under the draft tier
the gate queues each move for your approval — nothing moves until you say so.
Deterministic by design: it proposes, you decide.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, ProposedAction, Tile


class TidyFolder(Tile):
    async def run(self, input, context) -> ActionPlan:
        folder = str(input or ".").strip() or "."
        listing = await context.tools.call("list_dir", {"path": folder})
        if not listing.ok:
            return ActionPlan(result=f"Couldn't read '{folder}': {listing.error}")

        names = [
            n
            for n in str(listing.output).splitlines()
            if n and not n.endswith("/") and n != "(empty)"
        ]
        base = "" if folder in (".", "") else f"{folder.rstrip('/')}/"

        actions = []
        for name in names:
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else "other"
            actions.append(
                ProposedAction(
                    tool="move_file",
                    args={"src": f"{base}{name}", "dst": f"{base}{ext}/{name}"},
                    side_effect=True,
                    summary=f"Move {name} → {ext}/",
                )
            )

        if not actions:
            return ActionPlan(result=f"Nothing to tidy in '{folder}'.")
        return ActionPlan(
            result={"plan": f"Sort {len(actions)} file(s) into type folders"},
            actions=actions,
        )
