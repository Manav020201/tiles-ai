"""Ask My Files — read local documents (via MCP) and answer questions.

Demonstrates a tile over a real MCP-backed connector. The code is identical to
what it would be over a mock: list the directory and read files through
`ctx.tools` (allow-listed, read-only), then answer with `ctx.model`. No side
effects, true to its read_only tier.
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile

MAX_FILES = 8


class AskMyFiles(Tile):
    async def run(self, input, context) -> ActionPlan:
        listing = await context.tools.call("list_dir", {"path": "."})
        files = [
            name
            for name in str(listing.output).splitlines()
            if name and not name.endswith("/") and name != "(empty)"
        ]

        corpus = []
        for name in files[:MAX_FILES]:
            read = await context.tools.call("read_file", {"path": name})
            if read.ok:
                corpus.append(f"### {name}\n{read.output}")

        answer = await context.model.complete(
            f"Question: {input}\n\nDocuments:\n" + "\n\n".join(corpus),
            system=context.manifest.instructions,
        )
        return ActionPlan(result=answer)
