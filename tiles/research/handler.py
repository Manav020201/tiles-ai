"""Research — answer a question grounded in web search results. Read-only."""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile


class Research(Tile):
    async def run(self, input, context) -> ActionPlan:
        question = str(input or "").strip()
        if not question:
            return ActionPlan(result="Enter a question to research.")

        results = await context.tools.call("brave_web_search", {"query": question, "count": 8})
        sources = results.output if results.ok else "(search failed)"

        answer = await context.model.complete(
            f"Question: {question}\n\nWeb results:\n{sources}",
            system=context.manifest.instructions,
        )
        return ActionPlan(result=answer)
