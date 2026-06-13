"""End-to-end runtime over the REAL reference connector + tile on disk.

Doubles as the acceptance test for the inbox-summary reference tile: activate ->
run -> result, with the read tool routed through the bound mock connector and the
model resolved to the global default brain (the tile pins none). The brain runs
offline via the echo client, so no network is touched.
"""

import asyncio
from pathlib import Path

import pytest

from tiles_ai.contracts import (
    BrainResolutionError,
    HostedProvider,
    TileState,
)
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory
from tiles_ai.registry import Registry
from tiles_ai.runtime import Runtime, RuntimeError_, ToolDenied
from tiles_ai.runtime.handles import ToolProxy

REPO_ROOT = Path(__file__).resolve().parents[1]


def _runtime(with_default=True):
    store = BrainStore()
    if with_default:
        store.add_provider(
            HostedProvider(
                id="cloud", provider="anthropic", api_key="sk-test", model="claude-opus-4-8"
            ),
            make_default=True,
        )
    adapter = ModelAdapter(store, client_factory=echo_client_factory)
    reg = Registry.discover(REPO_ROOT)
    assert reg.ok, reg.report()
    assert "inbox-summary" in reg.tiles and "gmail" in reg.connectors
    return Runtime(reg, adapter)


def test_activate_run_deactivate_reference_tile():
    async def go():
        rt = _runtime()
        assert rt.state("inbox-summary") is TileState.AVAILABLE

        active = await rt.activate("inbox-summary")
        assert rt.is_active("inbox-summary")
        assert rt.state("inbox-summary") is TileState.ACTIVE
        # The tile pinned no model -> resolved to the global default brain.
        assert active.resolved_brain.source == "default"

        # Tool call routed through the bound connector returns the fake inbox.
        read = await active.context.tools.call("list_messages")
        assert read.ok and len(read.output) == 3

        outcome = await rt.run("inbox-summary")
        await rt.deactivate("inbox-summary")
        # Deactivated -> idle/loaded again (lifecycle stopped -> available),
        # i.e. not green on the board but ready to reactivate.
        assert not rt.is_active("inbox-summary")
        assert rt.state("inbox-summary") is TileState.AVAILABLE
        return outcome

    outcome = asyncio.run(go())
    # Echo proves the default brain (claude-opus-4-8) was the one invoked.
    assert outcome.result.startswith("[echo:claude-opus-4-8]")
    # read_only tile proposes nothing -> the gate has nothing to do.
    assert not outcome.gate.executed
    assert not outcome.gate.queued
    assert not outcome.gate.rejected


def test_activate_without_default_brain_raises():
    async def go():
        rt = _runtime(with_default=False)
        with pytest.raises(BrainResolutionError):
            await rt.activate("inbox-summary")

    asyncio.run(go())


def test_run_before_activate_raises():
    async def go():
        rt = _runtime()
        with pytest.raises(RuntimeError_):
            await rt.run("inbox-summary")

    asyncio.run(go())


def test_gate_is_the_only_path_to_side_effects():
    # The handler's RunContext exposes no raw connector — the field is gone and
    # the model rejects it — so a handler cannot fire a side effect inline.
    from pydantic import ValidationError
    from tiles_ai.contracts import RunContext, TileManifest

    async def go():
        rt = _runtime()
        active = await rt.activate("inbox-summary")
        assert not hasattr(active.context, "connector")

    asyncio.run(go())

    manifest = TileManifest.model_validate(
        {
            "id": "x",
            "name": "X",
            "description": "x",
            "instructions": "x",
            "permission_tier": "read_only",
        }
    )
    with pytest.raises(ValidationError):
        RunContext(manifest=manifest, connector="anything")  # forbidden field


def test_tool_proxy_denies_unlisted_and_side_effect_tools():
    async def go():
        rt = _runtime()
        await rt.activate("inbox-summary")
        tools: ToolProxy = rt._active["inbox-summary"].context.tools

        # send_message is neither allow-listed nor a read; both reasons deny it.
        with pytest.raises(ToolDenied):
            await tools.call("send_message", {"to": "a@b.com", "body": "hi"})

    asyncio.run(go())
