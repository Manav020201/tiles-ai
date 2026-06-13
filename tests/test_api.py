"""API integration tests over the real board, with an offline (echo) brain."""

from pathlib import Path

from fastapi.testclient import TestClient

from tiles_ai.api import create_app
from tiles_ai.contracts import HostedProvider
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client(with_default=True):
    store = BrainStore()
    if with_default:
        store.add_provider(
            HostedProvider(
                id="cloud", provider="anthropic", api_key="sk-test", model="claude-opus-4-8"
            ),
            make_default=True,
        )
    adapter = ModelAdapter(store, client_factory=echo_client_factory)
    app = create_app(root=REPO_ROOT, brain_store=store, model_adapter=adapter)
    return TestClient(app), app


def test_list_tiles_includes_references_with_brain_badge():
    client, _ = _client()
    tiles = client.get("/api/tiles").json()
    by_id = {t["id"]: t for t in tiles}
    assert {"inbox-summary", "reply-drafter"} <= set(by_id)

    inbox = by_id["inbox-summary"]
    assert inbox["permission_tier"] == "read_only"
    assert inbox["state"] == "available"
    assert inbox["uses_default_brain"] is True
    assert inbox["brain"]["source"] == "default"
    assert inbox["brain"]["model"] == "claude-opus-4-8"


def test_tile_detail_includes_instructions_and_capabilities():
    client, _ = _client()
    detail = client.get("/api/tiles/inbox-summary").json()
    assert detail["instructions"].strip().startswith("You summarize")
    assert detail["provides"][0]["name"] == "email.summary"
    assert detail["brain"]["source"] == "default"

    assert client.get("/api/tiles/does-not-exist").status_code == 404


def test_read_only_activate_run_flow():
    client, _ = _client()
    assert client.post("/api/tiles/inbox-summary/activate").json()["state"] == "active"
    run = client.post("/api/tiles/inbox-summary/run", json={"input": None}).json()
    assert run["result"].startswith("[echo:claude-opus-4-8]")
    assert run["queued"] == [] and run["rejected"] == []
    assert client.post("/api/tiles/inbox-summary/deactivate").json()["state"] == "available"


def test_draft_propose_queue_approve_flow():
    client, _ = _client()
    client.post("/api/tiles/reply-drafter/activate")

    run = client.post("/api/tiles/reply-drafter/run", json={}).json()
    assert len(run["queued"]) == 1
    assert run["queued"][0]["tool"] == "send_message"
    approval_id = run["queued"][0]["approval_id"]

    pending = client.get("/api/approvals").json()
    assert [p["id"] for p in pending] == [approval_id]
    assert pending[0]["side_effect"] is True
    assert pending[0]["status"] == "pending"

    resolved = client.post(
        f"/api/approvals/{approval_id}/resolve", json={"approved": True}
    ).json()
    assert resolved["status"] == "executed"
    assert resolved["output"]["status"] == "sent (mock)"

    # Queue drained.
    assert client.get("/api/approvals").json() == []


def test_draft_rejection_does_not_execute():
    client, _ = _client()
    client.post("/api/tiles/reply-drafter/activate")
    run = client.post("/api/tiles/reply-drafter/run", json={}).json()
    approval_id = run["queued"][0]["approval_id"]
    resolved = client.post(
        f"/api/approvals/{approval_id}/resolve", json={"approved": False}
    ).json()
    assert resolved["status"] == "rejected"
    assert resolved["output"] is None


def test_run_before_activate_is_409():
    client, _ = _client()
    assert client.post("/api/tiles/inbox-summary/run", json={}).status_code == 409


def test_activate_without_default_brain_is_409():
    client, _ = _client(with_default=False)
    resp = client.post("/api/tiles/inbox-summary/activate")
    assert resp.status_code == 409


def test_provider_management_and_test_action():
    client, _ = _client(with_default=False)
    # Add a local provider, make it default.
    body = {
        "provider": {
            "id": "local",
            "kind": "local",
            "endpoint": "http://localhost:11434",
            "model": "llama3",
        },
        "make_default": True,
    }
    providers = client.post("/api/providers", json=body).json()
    assert providers[0]["id"] == "local" and providers[0]["is_default"] is True
    # No api_key leaks in the view.
    assert "api_key" not in providers[0]

    # Test action runs through the (echo) client and reports ok.
    test = client.post("/api/providers/local/test").json()
    assert test["ok"] is True


def test_pin_brain_override():
    client, _ = _client()  # default = cloud (anthropic)
    # Add a local provider to pin to.
    client.post(
        "/api/providers",
        json={
            "provider": {
                "id": "local",
                "kind": "local",
                "endpoint": "http://localhost:11434",
                "model": "llama3",
            }
        },
    )
    # Before pin: inbox-summary uses the default brain.
    before = client.get("/api/tiles/inbox-summary").json()
    assert before["uses_default_brain"] is True
    assert before["brain"]["model"] == "claude-opus-4-8"

    # Pin it to the local provider.
    pinned = client.put(
        "/api/tiles/inbox-summary/brain", json={"provider_id": "local"}
    ).json()
    assert pinned["uses_default_brain"] is False
    assert pinned["brain"]["source"] == "pinned"
    assert pinned["brain"]["model"] == "llama3"

    # Clear the pin -> back to default.
    cleared = client.put(
        "/api/tiles/inbox-summary/brain", json={"provider_id": None}
    ).json()
    assert cleared["uses_default_brain"] is True
    assert cleared["brain"]["model"] == "claude-opus-4-8"


def test_events_endpoint_receives_activation_event():
    # Subscribe to the app's bus directly, then trigger an action over HTTP and
    # confirm the event was published (covers runtime->bus emission end to end
    # without depending on SSE streaming mechanics).
    client, app = _client()
    q = app.state.bus.subscribe()
    client.post("/api/tiles/inbox-summary/activate")
    event = q.get_nowait()
    assert event.type == "tile.activated"
    assert event.tile_id == "inbox-summary"
    assert event.data["tier"] == "read_only"
