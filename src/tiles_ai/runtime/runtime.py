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
from ..events import Event, EventBus
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
        events: EventBus | None = None,
    ) -> None:
        self.registry = registry
        self.model = model
        self.gate = gate or PermissionGate()
        self.events = events
        self._active: dict[str, ActiveTile] = {}
        # Per-tile brain overrides set from the UI (tile_id -> provider id). These
        # are session state, not manifest data, so they live here rather than on
        # disk; they win over a tile's pinned/default brain on next activation.
        self._brain_overrides: dict[str, str] = {}

    def _emit(self, type: str, tile_id: str | None = None, **data: Any) -> None:
        if self.events is not None:
            self.events.publish(Event(type=type, tile_id=tile_id, data=data))

    # --- introspection -----------------------------------------------------

    def state(self, tile_id: str) -> TileState:
        """Current lifecycle state of a tile (DEFINED if unknown to the registry)."""
        if tile_id in self._active:
            return self._active[tile_id].state
        loaded = self.registry.get_tile(tile_id)
        return loaded.state if loaded else TileState.DEFINED

    def is_active(self, tile_id: str) -> bool:
        return tile_id in self._active

    def resolve_brain_for(self, tile_id: str) -> ResolvedBrain:
        """Resolve a tile's brain, honoring a runtime override over the manifest.

        Order: UI override -> the tile's pinned `model` -> the global default.
        Raises BrainResolutionError if nothing resolves (no override, no pin, no
        default configured) — the case onboarding prevents.
        """
        loaded = self.registry.get_tile(tile_id)
        if loaded is None:
            raise RuntimeError_(f"no available tile '{tile_id}'")

        override_id = self._brain_overrides.get(tile_id)
        if override_id:
            provider = self.model.config.get(override_id)
            if provider is not None:
                return ResolvedBrain(
                    source="pinned",
                    provider=provider.provider_family(),
                    model=provider.model,
                    endpoint=getattr(provider, "endpoint", None),
                    provider_id=provider.id,
                )
            # Override points at a provider that no longer exists; drop it and
            # fall back to the manifest rather than failing.
            self._brain_overrides.pop(tile_id, None)
        return self.model.resolve(loaded.manifest.model)

    def set_brain_override(self, tile_id: str, provider_id: str | None) -> None:
        """Pin a tile to a configured provider (or clear the pin with None)."""
        if provider_id is None:
            self._brain_overrides.pop(tile_id, None)
            return
        if self.model.config.get(provider_id) is None:
            raise RuntimeError_(f"no provider '{provider_id}' to pin")
        self._brain_overrides[tile_id] = provider_id

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
        # which is exactly the case onboarding exists to prevent. A runtime
        # override (set from the tile's settings panel) wins over the manifest.
        resolved = self.resolve_brain_for(tile_id)

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
        # The raw connector is held on ActiveTile (runtime-internal, used by the
        # gate to execute approved actions). It is deliberately NOT placed on the
        # RunContext, so a handler cannot reach it to fire a side effect inline.
        context = RunContext(
            manifest=manifest,
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
        self._emit(
            "tile.activated",
            tile_id,
            brain=resolved.badge_label,
            tier=manifest.permission_tier.value,
        )
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

        for ex in gate_outcome.executed:
            self._emit("action.executed", tile_id, tool=ex.action.tool, ok=ex.result.ok)
        for item in gate_outcome.queued:
            self._emit(
                "action.queued",
                tile_id,
                approval_id=item.id,
                tool=item.action.tool,
                summary=item.action.summary,
            )
        for action in gate_outcome.rejected:
            self._emit("action.rejected", tile_id, tool=action.tool)
        self._emit(
            "tile.run",
            tile_id,
            executed=len(gate_outcome.executed),
            queued=len(gate_outcome.queued),
            rejected=len(gate_outcome.rejected),
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
        self._emit("tile.deactivated", tile_id)
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
        resolved = await self.gate.resolve(
            approval_id,
            approved,
            connector=connector,
            connector_manifest=connector_manifest,
        )
        self._emit(
            "approval.resolved",
            item.tile_id,
            approval_id=approval_id,
            approved=approved,
            status=resolved.status.value,
            tool=resolved.action.tool,
        )
        return resolved
