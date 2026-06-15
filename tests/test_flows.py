"""Multi-tile orchestration: provides/consumes matching + flow execution."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from tiles_ai.api import create_app
from tiles_ai.contracts import HostedProvider
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory
from tiles_ai.registry import Registry
from tiles_ai.runtime import Runtime
from tiles_ai.scaffold import scaffold_tile

REPO_ROOT = Path(__file__).resolve().parents[1]


def _echo_runtime(root):
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="c", provider="anthropic", api_key="k", model="claude-opus-4-8"),
        make_default=True,
    )
    reg = Registry.discover(root)
    return Runtime(reg, ModelAdapter(store, client_factory=echo_client_factory))


def _client():
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="c", provider="anthropic", api_key="k", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=REPO_ROOT,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
    )
    return TestClient(app)


def test_flow_candidates_match_provides_consumes():
    rt = _echo_runtime(REPO_ROOT)
    # inbox-summary provides email.summary; reply-drafter consumes it.
    assert "reply-drafter" in rt.flow_candidates("inbox-summary")["feeds"]
    assert "inbox-summary" in rt.flow_candidates("reply-drafter")["fed_by"]


def test_run_flow_pipes_result_into_next_input(tmp_path):
    scaffold_tile(tmp_path, id="a", name="A", instructions="A")
    scaffold_tile(tmp_path, id="b", name="B", instructions="B")
    rt = _echo_runtime(tmp_path)

    outcomes = asyncio.run(rt.run_flow(["a", "b"], "hello"))
    assert len(outcomes) == 2
    assert outcomes[0].result == "[echo:claude-opus-4-8] hello"
    # B's input was A's result, so B's echo wraps A's echo.
    assert outcomes[1].result == "[echo:claude-opus-4-8] [echo:claude-opus-4-8] hello"


def test_flow_endpoints():
    client = _client()
    flow = client.get("/api/tiles/inbox-summary/flow").json()
    assert "reply-drafter" in flow["feeds"]

    # Single-step flow.
    one = client.post("/api/flows/run", json={"tiles": ["ask"], "input": "hi"}).json()
    assert one["steps"][0]["result"] == "[echo:claude-opus-4-8] hi"

    # Real two-tile flow: summary -> drafter (which queues a send).
    two = client.post("/api/flows/run", json={"tiles": ["inbox-summary", "reply-drafter"]}).json()
    assert len(two["steps"]) == 2
    assert two["steps"][1]["queued"] == 1
