"""The runtime — activate, run, and deactivate tiles.

The runtime is the control plane's engine. It takes a loaded `Registry` plus a
`ModelAdapter`, and drives tiles through their lifecycle:

    activate(tile_id)   defined/available -> active (green)
    run(tile_id, input) execute the handler, route its ActionPlan through the gate
    deactivate(tile_id) active -> stopped

On activate it resolves the tile's brain (pin -> default), instantiates and
connects the bound connector (if any), instantiates the handler, and assembles
the `RunContext` (manifest, connector, resolved brain, `tools` proxy, `model`
handle). On run it hands the handler its input, then the permission gate decides
the fate of every proposed action. The runtime never executes a side effect
itself — the gate does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import (
    ActionPlan,
    Connector,
    ConnectorManifest,
    ResolvedBrain,
    RunContext,
    TileManifest,
    TileState,
    transition,
)
from ..model import ModelAdapter
from ..registry import Registry
from .gate import GateOutcome, PermissionGate
from .handles import ModelHandle, ToolProxy


@dataclass
class ActiveTile:
    """Everything the runtime holds for a tile that is currently green."""

    manifest: TileManifest
    handler: Any  # a Tile instance
    connector: Connector | None
    connector_manifest: ConnectorManifest | None
    resolved_brain: ResolvedBrain
    context: RunContext
    state: TileState = TileState.ACTIVE


@dataclass
class RunOutcome:
    """The result of one `run`: the tile's output plus what the gate did."""

    tile_id: str
    result: Any
    gate: GateOutcome


class RuntimeError_(Exception):
    """A runtime operation was invalid (unknown/inactive tile, etc.)."""


class Runtime:
    """Drives tiles through their lifecycle and routes their actions."""

    def __init__(
        self,
        registry: Registry,
        model: ModelAdapter,
        *,
        gate: PermissionGate | None = None,
    ) -> None:
        self.registry = registry
        self.model = model
        self.gate = gate or PermissionGate()
        self._active: dict[str, ActiveTile] = {}

    # --- introspection -----------------------------------------------------

    def state(self, tile_id: str) -> TileState:
        """Current lifecycle state of a tile (DEFINED if unknown to the registry)."""
        if tile_id in self._active:
            return self._active[tile_id].state
        loaded = self.registry.get_tile(tile_id)
        return loaded.state if loaded else TileState.DEFINED

    def is_active(self, tile_id: str) -> bool:
        return tile_id in self._active

    # --- lifecycle ---------------------------------------------------------

    async def activate(self, tile_id: str) -> ActiveTile:
        """Turn a tile green: resolve brain, connect, build context, on_activate."""
        if tile_id in self._active:
            return self._active[tile_id]

        loaded = self.registry.get_tile(tile_id)
        if loaded is None:
            raise RuntimeError_(f"no available tile '{tile_id}'")

        manifest = loaded.manifest
        # Resolve the brain first — a tile with no default configured fails here,
        # which is exactly the case onboarding exists to prevent.
        resolved = self.model.resolve(manifest.model)

        connector: Connector | None = None
        connector_manifest: ConnectorManifest | None = None
        tools: ToolProxy | None = None
        if manifest.connector:
            lc = self.registry.get_connector(manifest.connector)
            if lc is None:  # registry should have rejected this; be defensive
                raise RuntimeError_(
                    f"tile '{tile_id}' binds missing connector '{manifest.connector}'"
                )
            connector_manifest = lc.manifest
            connector = lc.adapter_cls.from_manifest(lc.manifest)
            await connector.connect(lc.manifest.auth)
            tools = ToolProxy(
                tile_id=tile_id,
                allowed_tools=manifest.allowed_tools,
                connector=connector,
                connector_manifest=lc.manifest,
            )

        handler = loaded.handler_cls(manifest)
        context = RunContext(
            manifest=manifest,
            connector=connector,
            resolved_brain=resolved,
            tools=tools,
            model=ModelHandle(self.model, resolved),
        )

        validation = await handler.validate(context)
        if not validation.ok:
            if connector is not None:
                await connector.disconnect()
            raise RuntimeError_(
                f"tile '{tile_id}' failed validation: {'; '.join(validation.errors)}"
            )

        await handler.on_activate(context)
        transition(loaded.state, TileState.ACTIVE)  # guard: available -> active

        active = ActiveTile(
            manifest=manifest,
            handler=handler,
            connector=connector,
            connector_manifest=connector_manifest,
            resolved_brain=resolved,
            context=context,
        )
        self._active[tile_id] = active
        return active

    async def run(self, tile_id: str, input: Any = None) -> RunOutcome:
        """Execute an active tile's handler and route its plan through the gate."""
        active = self._active.get(tile_id)
        if active is None:
            raise RuntimeError_(f"tile '{tile_id}' is not active; activate it first")

        plan: ActionPlan = await active.handler.run(input, active.context)
        gate_outcome = await self.gate.process(
            tile_id=tile_id,
            tier=active.manifest.permission_tier,
            actions=plan.actions,
            connector=active.connector,
            connector_manifest=active.connector_manifest,
        )
        return RunOutcome(tile_id=tile_id, result=plan.result, gate=gate_outcome)

    async def deactivate(self, tile_id: str) -> None:
        """Stop a tile: on_deactivate, disconnect, drop activation state."""
        active = self._active.pop(tile_id, None)
        if active is None:
            return
        await active.handler.on_deactivate()
        if active.connector is not None:
            await active.connector.disconnect()
        # The tile is dropped from the active set; the registry keeps it as
        # `available` (loaded, idle), so it can be reactivated. `stopped` is the
        # transient teardown state, not a resting one we track per board.

    # --- approvals (delegated to the gate, with the right connector wired) ---

    def pending_approvals(self, tile_id: str | None = None):
        return self.gate.pending(tile_id)

    async def resolve_approval(self, approval_id: str, approved: bool):
        """Approve/reject a queued action, executing it on the tile's connector."""
        item = self.gate.get(approval_id)
        if item is None:
            raise RuntimeError_(f"no approval '{approval_id}'")
        active = self._active.get(item.tile_id)
        connector = active.connector if active else None
        connector_manifest = active.connector_manifest if active else None
        return await self.gate.resolve(
            approval_id,
            approved,
            connector=connector,
            connector_manifest=connector_manifest,
        )
