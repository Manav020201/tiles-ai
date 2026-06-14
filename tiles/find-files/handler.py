"""Find Files — search local files by name. Read-only, zero-credential.

Returns the matches directly from the connector (no model needed) — a tile is
free to skip the brain when a tool answers the question.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class FindFiles(Tile):
    async def run(self, input, context) -> ActionPlan:
        query = str(input or "").strip()
        if not query:
            return ActionPlan(result="Type a filename or keyword to find.")

        result = await context.tools.call("find_files", {"query": query})
        if not result.ok:
            return ActionPlan(result=f"Search failed: {result.error}")
        return ActionPlan(result=result.output)
