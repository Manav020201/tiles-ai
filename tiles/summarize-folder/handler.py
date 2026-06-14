"""Summarize Folder — read a local folder and describe what's in it. Read-only.

A zero-credential "smart PC" tile: it reads through the local-files connector and
summarizes. Input is a folder path relative to the connector's root (blank = root).
"""

from __future__ import annotations

from tiles_ai.contracts import ActionPlan, Tile

MAX_PREVIEWS = 6


class SummarizeFolder(Tile):
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

        previews = []
        for name in names[:MAX_PREVIEWS]:
            read = await context.tools.call("read_file", {"path": f"{base}{name}"})
            if read.ok:
                previews.append(f"### {name}\n{str(read.output)[:600]}")

        summary = await context.model.complete(
            f"Folder '{folder}' listing:\n{listing.output}\n\nFile previews:\n"
            + "\n\n".join(previews),
            system=context.manifest.instructions,
        )
        return ActionPlan(result=summary)
