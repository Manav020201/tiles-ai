"""Exercise the async Connector/Tile interfaces against tiny reference impls.

This proves the contract is *implementable* and that the propose -> gate flow
works end to end at the contract level (the real runtime arrives in phase 3).
Tests drive async code with asyncio.run to avoid a pytest-asyncio dependency.
"""

import asyncio

from tiles_ai.contracts import (
    ActionPlan,
    AuthConfig,
    CallContext,
    Connector,
    PermissionDecision,
    PermissionTier,
    ProposedAction,
    RunContext,
    Session,
    Tile,
    TileManifest,
    ToolResult,
    ToolSpec,
    evaluate,
)


class FakeConnector(Connector):
    """In-process connector with one read tool and one side-effectful tool."""

    async def connect(self, auth: AuthConfig) -> Session:
        return Session(connector_id=self.manifest_id)

    async def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name="list_messages", description="List", side_effect=False),
            ToolSpec(name="send_message", description="Send", side_effect=True),
        ]

    async def call_tool(self, name: str, args: dict, context: CallContext) -> ToolResult:
        if name == "list_messages":
            return ToolResult(ok=True, output=["msg-1", "msg-2"], side_effect=False)
        if name == "send_message":
            return ToolResult(ok=True, output="sent", side_effect=True)
        return ToolResult(ok=False, error=f"unknown tool {name}", side_effect=False)


class DraftTile(Tile):
    """A draft-tier tile: reads, then proposes a side-effectful reply."""

    async def run(self, input, context: RunContext) -> ActionPlan:
        return ActionPlan(
            result="2 unread messages",
            actions=[
                ProposedAction(
                    tool="send_message",
                    args={"to": "a@b.com", "body": "thanks"},
                    side_effect=True,
                    summary="Reply to a@b.com",
                )
            ],
        )


def _manifest():
    return TileManifest.model_validate(
        {
            "id": "reply-drafter",
            "name": "Reply Drafter",
            "description": "Draft replies",
            "connector": "gmail",
            "instructions": "Draft a reply.",
            "allowed_tools": ["list_messages", "send_message"],
            "permission_tier": "draft",
        }
    )


def test_connector_roundtrip():
    async def go():
        c = FakeConnector("gmail")
        session = await c.connect(AuthConfig())
        assert session.connected
        tools = await c.list_tools()
        assert {t.name for t in tools} == {"list_messages", "send_message"}

        ctx = CallContext(tile_id="reply-drafter", allowed_tools=["list_messages"])
        read = await c.call_tool("list_messages", {}, ctx)
        assert read.ok and read.side_effect is False
        write = await c.call_tool("send_message", {}, ctx)
        assert write.ok and write.side_effect is True

    asyncio.run(go())


def test_draft_tile_proposes_action_that_gate_queues():
    async def go():
        manifest = _manifest()
        tile = DraftTile(manifest)
        ctx = RunContext(manifest=manifest)
        await tile.on_activate(ctx)
        plan = await tile.run("go", ctx)
        await tile.on_deactivate()
        return plan

    plan = asyncio.run(go())
    assert plan.has_side_effects
    # The contract's gate policy queues a draft tile's side effect for approval.
    action = plan.actions[0]
    decision = evaluate(PermissionTier.DRAFT, action.side_effect)
    assert decision is PermissionDecision.QUEUE


def test_read_only_tile_proposing_side_effect_is_rejected_by_gate():
    # Even if a handler misbehaves, the gate is the backstop.
    action = ProposedAction(tool="send_message", side_effect=True)
    decision = evaluate(PermissionTier.READ_ONLY, action.side_effect)
    assert decision is PermissionDecision.REJECT
