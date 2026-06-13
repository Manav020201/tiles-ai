"""Handler-facing handles: `ctx.tools` and `ctx.model`.

These are the ergonomic surface a tile author actually touches. They keep
handlers short and safe:

  * ToolProxy enforces the allow-list and refuses inline side effects, so a
    handler can *read* through its connector but must *propose* anything that
    touches the world.
  * ModelHandle binds the tile's resolved brain so a handler just calls
    `await ctx.model.complete(prompt)` without knowing which provider won.
"""

from __future__ import annotations

from ..contracts import CallContext, Connector, ConnectorManifest, ResolvedBrain, ToolResult


class ToolDenied(Exception):
    """A handler tried to call a tool it may not call inline."""


class ToolProxy:
    """Allow-list-enforcing, read-only access to a tile's connector tools."""

    def __init__(
        self,
        *,
        tile_id: str,
        allowed_tools: list[str],
        connector: Connector,
        connector_manifest: ConnectorManifest,
    ) -> None:
        self._tile_id = tile_id
        self._allowed = set(allowed_tools)
        self._connector = connector
        self._manifest = connector_manifest

    async def call(self, name: str, args: dict | None = None) -> ToolResult:
        """Call a read tool through the connector. Side effects must be proposed.

        Raises ToolDenied if the tool isn't allow-listed, or if it is
        side-effectful — those must flow through the ActionPlan and the gate, not
        be executed inline by the handler.
        """
        if name not in self._allowed:
            raise ToolDenied(
                f"tile '{self._tile_id}' may not call '{name}'. "
                f"Allow-listed: {sorted(self._allowed)}."
            )
        spec = self._manifest.get_tool(name)
        if spec is not None and spec.side_effect:
            raise ToolDenied(
                f"tool '{name}' is side-effectful; propose it as an action so the "
                "permission gate can decide, don't call it inline."
            )
        ctx = CallContext(tile_id=self._tile_id, allowed_tools=sorted(self._allowed))
        return await self._connector.call_tool(name, args or {}, ctx)


class ModelHandle:
    """Binds the runtime's model adapter to a tile's resolved brain."""

    def __init__(self, adapter: "object", resolved: ResolvedBrain) -> None:
        # adapter typed loosely to avoid importing the model layer into a module
        # the contract-facing handler sees; it is always a ModelAdapter.
        self._adapter = adapter
        self._resolved = resolved

    @property
    def resolved(self) -> ResolvedBrain:
        return self._resolved

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        return await self._adapter.complete(self._resolved, prompt, system=system)
