"""Reusable Tile base classes for the common cases.

`PromptTile` is the entire body of an "instant" tile: it runs the user's input
through the brain, using the tile's manifest `instructions` as the system prompt,
and returns the completion. No connector, no side effects — it works the moment a
brain is connected.

With it, an instant tile's handler is a one-liner and the *manifest* is the tile:

    from tiles_ai.handlers import PromptTile

    class Ask(PromptTile):
        '''General Q&A — behavior comes from the manifest instructions.'''

Differentiate instant tiles by their `instructions`, not by code. (Tiles that
read from an app or propose side effects still implement `run` directly — see
tiles/inbox-summary and tiles/reply-drafter.)
"""

from __future__ import annotations

from typing import Any

from .contracts import ActionPlan, RunContext, Tile


class PromptTile(Tile):
    """A connector-free tile: input -> brain -> result.

    The user's input is the prompt; the manifest's `instructions` are the system
    prompt. Returns the completion with no proposed actions, so it is inherently
    read_only — nothing reaches the permission gate.
    """

    async def run(self, input: Any, context: RunContext) -> ActionPlan:
        prompt = "" if input is None else str(input)
        completion = await context.model.complete(prompt, system=context.manifest.instructions)
        return ActionPlan(result=completion)
