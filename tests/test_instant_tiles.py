"""Instant tiles: connector-free PromptTile reference tiles + starter board."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from tiles_ai.api import create_app
from tiles_ai.contracts import HostedProvider
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory
from tiles_ai.registry import Registry
from tiles_ai.runtime import Runtime

REPO_ROOT = Path(__file__).resolve().parents[1]

INSTANT_IDS = {"ask", "summarize", "translate", "extract", "brainstorm"}


def _runtime():
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="cloud", provider="anthropic", api_key="sk", model="claude-opus-4-8"),
        make_default=True,
    )
    reg = Registry.discover(REPO_ROOT)
    assert reg.ok, reg.report()
    return Runtime(reg, ModelAdapter(store, client_factory=echo_client_factory))


def test_all_instant_tiles_load():
    reg = Registry.discover(REPO_ROOT)
    assert reg.ok, reg.report()
    assert INSTANT_IDS <= set(reg.tiles)
    for tid in INSTANT_IDS:
        tile = reg.tiles[tid]
        assert tile.manifest.connector is None  # no app
        assert tile.manifest.allowed_tools == []
        assert tile.manifest.permission_tier.value == "read_only"


def test_instant_tile_activate_run_with_input():
    async def go():
        rt = _runtime()
        await rt.activate("ask")
        outcome = await rt.run("ask", "What is 2+2?")
        await rt.deactivate("ask")
        return outcome

    outcome = asyncio.run(go())
    # Echo proves input reached the model with the default brain; no actions.
    assert outcome.result == "[echo:claude-opus-4-8] What is 2+2?"
    assert not outcome.gate.executed and not outcome.gate.queued


def test_api_marks_instant_tiles_wants_input():
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="cloud", provider="anthropic", api_key="sk", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=REPO_ROOT,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
    )
    client = TestClient(app)
    tiles = {t["id"]: t for t in client.get("/api/tiles").json()}

    ask = tiles["ask"]
    assert ask["wants_input"] is True
    assert ask["input_hint"]  # non-empty placeholder
    assert ask["connector"] is None

    # An app tile that takes no freeform input is not marked.
    assert tiles["inbox-summary"]["wants_input"] is False


def test_api_run_instant_tile_with_input():
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="cloud", provider="anthropic", api_key="sk", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=REPO_ROOT,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
    )
    client = TestClient(app)
    client.post("/api/tiles/summarize/activate")
    run = client.post("/api/tiles/summarize/run", json={"input": "a long article"}).json()
    assert run["result"] == "[echo:claude-opus-4-8] a long article"
