"""Web Search — search the web and digest the results. Read-only."""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class WebSearch(Tile):
    async def run(self, input, context) -> ActionPlan:
        query = str(input or "").strip()
        if not query:
            return ActionPlan(result="Enter something to search for.")

        results = await context.tools.call("brave_web_search", {"query": query, "count": 8})
        if not results.ok:
            return ActionPlan(result=f"Search failed: {results.error}")

        digest = await context.model.complete(
            f"Search query: {query}\n\nResults:\n{results.output}",
            system=context.manifest.instructions,
        )
        return ActionPlan(result=digest)
