"""The Tile interface — `tiles/<id>/handler.py` implements this.

The handler is the agent's body. The runtime drives it through the lifecycle:
`validate` (load time) -> `on_activate` (turned green) -> `run` (per input) ->
`on_deactivate` (turned off).

`run` returns an `ActionPlan`: a result plus a list of *proposed* actions. Each
action carries a `side_effect` flag. The handler never executes side effects
itself — it proposes them, and the central permission gate (phase 3) decides,
per the tile's `permission_tier`, whether each one executes, queues for
approval, or is rejected. This is what makes "green = running, not
unsupervised" a structural guarantee rather than a convention.

Interfaces are async to match the connector layer and the runtime.
"""

from __future__ import annotations

import abc
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .tile_manifest import TileManifest


class ValidationResult(BaseModel):
    """Outcome of a handler's self-check at load time."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(ok=True)

    @classmethod
    def failure(cls, *errors: str) -> ValidationResult:
        return cls(ok=False, errors=list(errors))


class ProposedAction(BaseModel):
    """One action a tile proposes as part of its result.

    Side-effectful actions do not run here — they pass through the permission
    gate. A `read_only` tile should only ever propose `side_effect=False`
    actions; if it proposes a side-effectful one the gate rejects it.
    """

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(description="Connector tool this action would invoke.")
    args: dict = Field(default_factory=dict, description="Arguments for the tool.")
    side_effect: bool = Field(
        default=False,
        description="Whether executing this action touches the outside world.",
    )
    summary: str = Field(
        default="",
        description="Human-readable description for the approval queue / activity feed.",
    )


class ActionPlan(BaseModel):
    """What a tile's `run` returns: a result plus any proposed actions."""

    model_config = ConfigDict(extra="forbid")

    result: Any = Field(
        default=None,
        description="The tile's direct output (a summary, an answer, structured data).",
    )
    actions: list[ProposedAction] = Field(
        default_factory=list,
        description="Side-effectful or follow-up actions proposed for the gate.",
    )

    @property
    def has_side_effects(self) -> bool:
        return any(a.side_effect for a in self.actions)


class RunContext(BaseModel):
    """Everything a handler needs at run time, assembled by the runtime.

    The handler receives its resolved manifest, a read-only `tools` handle, a
    `model` handle, and the resolved brain descriptor. It does NOT receive raw
    secrets, and — deliberately — it does NOT receive the raw connector. A
    handler therefore has exactly two ways to touch the world:

      * read via `ctx.tools` (allow-listed, non-side-effectful only), and
      * propose side effects via the returned `ActionPlan`.

    The permission gate is the single path through which any side effect can
    actually execute. Removing the raw connector from this context is what makes
    that a structural guarantee instead of a convention a handler could ignore.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    manifest: TileManifest
    resolved_brain: Any = None  # ResolvedBrain; typed Any to avoid an import cycle.

    tools: Any = None
    """Allow-list-enforcing handle for *reading* through the bound connector.

    `await ctx.tools.call(name, args)` routes to the connector, but only for
    tools in `allowed_tools` and only for non-side-effectful ones — a handler
    must *propose* side effects via the returned ActionPlan, never execute them
    inline. None for instant tiles (no connector). Wired by the runtime; typed
    Any to keep the contract free of a runtime import.
    """

    model: Any = None
    """Handle to the tile's resolved brain.

    `await ctx.model.complete(prompt, system=...)` calls whatever model resolved
    for this tile (its pin, or the global default). Wired by the runtime.
    """


class Tile(abc.ABC):
    """Base class every tile handler implements.

    The target experience: a developer copies a reference tile's folder,
    implements `run`, and has a working tile. Keep concrete handlers short and
    readable — that is the whole product thesis.
    """

    def __init__(self, manifest: TileManifest) -> None:
        self.manifest = manifest

    async def validate(self, context: RunContext) -> ValidationResult:
        """Sanity-check manifest + config. Default: pass. Override to add checks."""
        return ValidationResult.success()

    async def on_activate(self, context: RunContext) -> None:
        """Set up resources when the tile turns green. Default no-op."""
        return None

    @abc.abstractmethod
    async def run(self, input: Any, context: RunContext) -> ActionPlan:
        """Produce a result and/or a list of proposed actions for one input.

        MUST flag side-effectful actions via `ProposedAction.side_effect`. MUST
        NOT execute side effects directly — propose them and let the gate decide.
        """

    async def on_deactivate(self) -> None:
        """Tear down resources when the tile is stopped. Default no-op."""
        return None
