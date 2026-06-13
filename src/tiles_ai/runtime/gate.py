"""The permission gate — the single enforcement point for side effects.

Every action a tile proposes passes through here. The gate consults the one
policy function (`contracts.permissions.evaluate`) for the tile's tier and:

  * EXECUTE -> runs the action now (routed through the bound connector),
  * QUEUE   -> parks it in the approval queue for a human,
  * REJECT  -> refuses it (a read_only tile tried to touch the world).

Queued actions are executed later via `resolve()` when a human approves. This is
what makes "green = running, not unsupervised" structural: a handler can only
*propose* side effects; whether they fire is decided here, never by the tile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..contracts import (
    CallContext,
    Connector,
    ConnectorManifest,
    PermissionDecision,
    PermissionTier,
    ProposedAction,
    ToolResult,
    evaluate,
)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"


@dataclass
class ApprovalItem:
    """One side-effectful action awaiting (or past) a human decision."""

    id: str
    tile_id: str
    action: ProposedAction
    status: ApprovalStatus = ApprovalStatus.PENDING
    result: ToolResult | None = None
    note: str = ""


@dataclass
class ExecutedAction:
    """A proposed action that the gate executed, paired with its result."""

    action: ProposedAction
    result: ToolResult


@dataclass
class GateOutcome:
    """What the gate did with a single run's worth of proposed actions."""

    executed: list[ExecutedAction] = field(default_factory=list)
    queued: list[ApprovalItem] = field(default_factory=list)
    rejected: list[ProposedAction] = field(default_factory=list)


class PermissionGate:
    """Holds the approval queue and enforces tiers over proposed actions."""

    def __init__(self) -> None:
        self._items: dict[str, ApprovalItem] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"appr-{self._counter}"

    async def process(
        self,
        *,
        tile_id: str,
        tier: PermissionTier,
        actions: list[ProposedAction],
        connector: Connector | None,
        connector_manifest: ConnectorManifest | None,
    ) -> GateOutcome:
        """Run each proposed action through the tier policy."""
        outcome = GateOutcome()
        # Declaring a tile `autonomous` IS the opt-in to direct execution, so we
        # treat that tier as standing approval. `draft` always queues; read_only
        # rejects.
        approved = tier is PermissionTier.AUTONOMOUS
        for action in actions:
            decision = evaluate(tier, action.side_effect, approved=approved)
            if decision is PermissionDecision.EXECUTE:
                result = await self._execute(
                    tile_id, action, connector, connector_manifest
                )
                outcome.executed.append(ExecutedAction(action, result))
            elif decision is PermissionDecision.QUEUE:
                item = ApprovalItem(self._next_id(), tile_id, action)
                self._items[item.id] = item
                outcome.queued.append(item)
            else:  # REJECT
                outcome.rejected.append(action)
        return outcome

    def pending(self, tile_id: str | None = None) -> list[ApprovalItem]:
        """Approval items still awaiting a human, optionally filtered by tile."""
        return [
            i
            for i in self._items.values()
            if i.status is ApprovalStatus.PENDING
            and (tile_id is None or i.tile_id == tile_id)
        ]

    def get(self, approval_id: str) -> ApprovalItem | None:
        return self._items.get(approval_id)

    async def resolve(
        self,
        approval_id: str,
        approved: bool,
        *,
        connector: Connector | None,
        connector_manifest: ConnectorManifest | None,
    ) -> ApprovalItem:
        """Approve (and execute) or reject a queued action."""
        item = self._items.get(approval_id)
        if item is None:
            raise KeyError(f"no approval '{approval_id}'")
        if item.status is not ApprovalStatus.PENDING:
            raise ValueError(f"approval '{approval_id}' already {item.status.value}")

        if not approved:
            item.status = ApprovalStatus.REJECTED
            item.note = "rejected by human"
            return item

        item.result = await self._execute(
            item.tile_id, item.action, connector, connector_manifest
        )
        item.status = ApprovalStatus.EXECUTED
        return item

    async def _execute(
        self,
        tile_id: str,
        action: ProposedAction,
        connector: Connector | None,
        connector_manifest: ConnectorManifest | None,
    ) -> ToolResult:
        if connector is None:
            return ToolResult(
                ok=False,
                error=f"action '{action.tool}' has no bound connector to execute on",
                side_effect=action.side_effect,
            )
        allowed = list(connector_manifest.tool_names()) if connector_manifest else []
        ctx = CallContext(tile_id=tile_id, allowed_tools=allowed)
        return await connector.call_tool(action.tool, action.args, ctx)
