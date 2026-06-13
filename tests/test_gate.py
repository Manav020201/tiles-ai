import asyncio

from tiles_ai.connectors import MockConnector
from tiles_ai.contracts import ConnectorManifest, PermissionTier, ProposedAction
from tiles_ai.runtime import ApprovalStatus, PermissionGate


def _connector():
    manifest = ConnectorManifest.model_validate(
        {
            "id": "gmail",
            "app": "Gmail",
            "kind": "mock",
            "tools": [
                {"name": "list_messages", "description": "List", "side_effect": False},
                {"name": "send_message", "description": "Send", "side_effect": True},
            ],
        }
    )
    conn = MockConnector.from_manifest(manifest)
    conn.set_response("send_message", {"status": "sent"})
    conn.set_response("list_messages", ["m1"])
    return conn, manifest


def _send(**args):
    return ProposedAction(tool="send_message", args=args, side_effect=True, summary="send")


def test_non_side_effect_executes_inline():
    async def go():
        conn, manifest = _connector()
        gate = PermissionGate()
        action = ProposedAction(tool="list_messages", side_effect=False)
        return await gate.process(
            tile_id="t",
            tier=PermissionTier.READ_ONLY,
            actions=[action],
            connector=conn,
            connector_manifest=manifest,
        )

    out = asyncio.run(go())
    assert len(out.executed) == 1 and out.executed[0].ok
    assert not out.queued and not out.rejected


def test_read_only_side_effect_rejected():
    async def go():
        conn, manifest = _connector()
        gate = PermissionGate()
        return await gate.process(
            tile_id="t",
            tier=PermissionTier.READ_ONLY,
            actions=[_send(to="a@b.com", body="hi")],
            connector=conn,
            connector_manifest=manifest,
        )

    out = asyncio.run(go())
    assert len(out.rejected) == 1
    assert not out.executed and not out.queued


def test_draft_queues_then_executes_on_approval():
    async def go():
        conn, manifest = _connector()
        gate = PermissionGate()
        out = await gate.process(
            tile_id="t",
            tier=PermissionTier.DRAFT,
            actions=[_send(to="a@b.com", body="hi")],
            connector=conn,
            connector_manifest=manifest,
        )
        assert len(out.queued) == 1 and not out.executed
        item = out.queued[0]
        assert [i.id for i in gate.pending("t")] == [item.id]

        resolved = await gate.resolve(item.id, True, connector=conn, connector_manifest=manifest)
        return gate, resolved

    gate, resolved = asyncio.run(go())
    assert resolved.status is ApprovalStatus.EXECUTED
    assert resolved.result.ok and resolved.result.output == {"status": "sent"}
    assert gate.pending() == []  # queue drained


def test_draft_rejection_does_not_execute():
    async def go():
        conn, manifest = _connector()
        gate = PermissionGate()
        out = await gate.process(
            tile_id="t",
            tier=PermissionTier.DRAFT,
            actions=[_send(to="a@b.com", body="hi")],
            connector=conn,
            connector_manifest=manifest,
        )
        item = out.queued[0]
        return await gate.resolve(item.id, False, connector=conn, connector_manifest=manifest)

    resolved = asyncio.run(go())
    assert resolved.status is ApprovalStatus.REJECTED
    assert resolved.result is None


def test_autonomous_executes_directly():
    async def go():
        conn, manifest = _connector()
        gate = PermissionGate()
        return await gate.process(
            tile_id="t",
            tier=PermissionTier.AUTONOMOUS,
            actions=[_send(to="a@b.com", body="hi")],
            connector=conn,
            connector_manifest=manifest,
        )

    out = asyncio.run(go())
    assert len(out.executed) == 1 and out.executed[0].ok
    assert not out.queued and not out.rejected


def test_double_resolve_is_error():
    async def go():
        conn, manifest = _connector()
        gate = PermissionGate()
        out = await gate.process(
            tile_id="t",
            tier=PermissionTier.DRAFT,
            actions=[_send(to="a@b.com", body="hi")],
            connector=conn,
            connector_manifest=manifest,
        )
        item = out.queued[0]
        await gate.resolve(item.id, True, connector=conn, connector_manifest=manifest)
        try:
            await gate.resolve(item.id, True, connector=conn, connector_manifest=manifest)
        except ValueError:
            return "rejected-second"
        return "allowed-second"

    assert asyncio.run(go()) == "rejected-second"
