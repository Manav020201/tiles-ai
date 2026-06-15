"""API integration tests over the real board, with an offline (echo) brain."""

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from tiles_ai.api import create_app
from tiles_ai.contracts import HostedProvider
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER = REPO_ROOT / "examples" / "mcp_servers" / "files_server.py"


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

    resolved = client.post(f"/api/approvals/{approval_id}/resolve", json={"approved": True}).json()
    assert resolved["status"] == "executed"
    assert resolved["output"]["status"] == "sent (mock)"

    # Queue drained.
    assert client.get("/api/approvals").json() == []


def test_draft_rejection_does_not_execute():
    client, _ = _client()
    client.post("/api/tiles/reply-drafter/activate")
    run = client.post("/api/tiles/reply-drafter/run", json={}).json()
    approval_id = run["queued"][0]["approval_id"]
    resolved = client.post(f"/api/approvals/{approval_id}/resolve", json={"approved": False}).json()
    assert resolved["status"] == "rejected"
    assert resolved["output"] is None


def test_run_before_activate_is_409():
    client, _ = _client()
    assert client.post("/api/tiles/inbox-summary/run", json={}).status_code == 409


def test_model_failure_returns_clean_502():
    # An upstream model error (e.g. Anthropic 529 after retries) must surface as a
    # clean 502, not a 500 traceback.
    from tiles_ai.model import ModelClientError

    class _FailingClient:
        async def complete(self, prompt, *, system=None):
            raise ModelClientError("HTTP 529 from api.anthropic.com: Overloaded")

    store = BrainStore()
    store.add_provider(
        HostedProvider(id="cloud", provider="anthropic", api_key="sk", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=REPO_ROOT,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=lambda r, c: _FailingClient()),
    )
    client = TestClient(app)
    client.post("/api/tiles/ask/activate")
    resp = client.post("/api/tiles/ask/run", json={"input": "hi"})
    assert resp.status_code == 502
    assert "529" in resp.json()["detail"]


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

    # In offline (echo) mode the test action is honest: it does NOT claim the key
    # works, since every call would just echo.
    test = client.post("/api/providers/local/test").json()
    assert test["ok"] is False
    assert "--echo" in test["detail"]


def test_provider_test_reports_ok_with_a_real_brain(tmp_path):
    # Outside echo mode, a working brain reports ok. Use a stub client so the test
    # stays offline without pretending to be echo.
    class _OkClient:
        async def complete(self, prompt, *, system=None):
            return "ok"

    store = BrainStore.load(tmp_path / "brain.local.yaml")
    store.add_provider(
        HostedProvider(id="cloud", provider="anthropic", api_key="sk", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=REPO_ROOT,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=lambda r, c: _OkClient()),
    )
    test = TestClient(app).post("/api/providers/cloud/test").json()
    assert test["ok"] is True and test["detail"] == "ok"


def test_brain_changes_persist_to_disk(tmp_path):
    # A path-backed store (the real `tiles up` case) must save UI changes so the
    # provider survives a restart — regression test for the add/save gap.
    brain_file = tmp_path / "brain.local.yaml"
    store = BrainStore.load(brain_file)  # absent file -> empty store with a path
    app = create_app(
        root=REPO_ROOT,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
    )
    client = TestClient(app)

    assert not brain_file.exists()
    client.post(
        "/api/providers",
        json={
            "provider": {
                "id": "cloud",
                "kind": "hosted",
                "provider": "anthropic",
                "api_key": "sk-real",
                "model": "claude-opus-4-8",
            },
            "make_default": True,
        },
    )

    # Written to disk, and a fresh load sees the provider + default.
    assert brain_file.exists()
    reloaded = BrainStore.load(brain_file)
    assert reloaded.config.default_provider == "cloud"
    assert reloaded.config.get("cloud").api_key == "sk-real"


def test_connector_secrets_set_from_the_board(tmp_path, monkeypatch):
    # Entering a connector API key in the UI persists it (temp board, not the
    # repo) and clears the connector's "needs token" state.
    monkeypatch.delenv("TILES_TEST_BRAVE_KEY", raising=False)
    conn = tmp_path / "connectors" / "demo"
    conn.mkdir(parents=True)
    (conn / "manifest.yaml").write_text(
        "id: demo\napp: Demo\nkind: mock\n"
        "auth:\n  scheme: api_key\n  env: [TILES_TEST_BRAVE_KEY]\n"
        "tools:\n  - {name: ping, description: p, side_effect: false}\n"
    )
    (conn / "adapter.py").write_text(
        "from tiles_ai.connectors import MockConnector\n\n\nclass Demo(MockConnector):\n    pass\n"
    )
    client = TestClient(create_app(root=tmp_path, brain_store=BrainStore()))

    before = next(c for c in client.get("/api/connectors").json() if c["id"] == "demo")
    assert before["missing_env"] == ["TILES_TEST_BRAVE_KEY"]

    updated = client.put(
        "/api/connectors/demo/secrets",
        json={"values": {"TILES_TEST_BRAVE_KEY": "sk-brave"}},
    ).json()
    assert updated["missing_env"] == []
    assert os.environ["TILES_TEST_BRAVE_KEY"] == "sk-brave"
    assert (tmp_path / "secrets.local.yaml").exists()  # written to the board, not the repo

    # An env var the connector doesn't declare is rejected.
    assert (
        client.put("/api/connectors/demo/secrets", json={"values": {"NOPE": "x"}}).status_code
        == 400
    )

    cleared = client.delete("/api/connectors/demo/secrets/TILES_TEST_BRAVE_KEY").json()
    assert cleared["missing_env"] == ["TILES_TEST_BRAVE_KEY"]
    monkeypatch.delenv("TILES_TEST_BRAVE_KEY", raising=False)


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
    pinned = client.put("/api/tiles/inbox-summary/brain", json={"provider_id": "local"}).json()
    assert pinned["uses_default_brain"] is False
    assert pinned["brain"]["source"] == "pinned"
    assert pinned["brain"]["model"] == "llama3"

    # Clear the pin -> back to default.
    cleared = client.put("/api/tiles/inbox-summary/brain", json={"provider_id": None}).json()
    assert cleared["uses_default_brain"] is True
    assert cleared["brain"]["model"] == "claude-opus-4-8"


def test_connector_readiness_reflects_required_env(monkeypatch):
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    client, _ = _client()
    tiles = {t["id"]: t for t in client.get("/api/tiles").json()}

    # GitHub tiles need a token that isn't set -> not ready.
    gh = tiles["github-triage"]
    assert gh["connector_ready"] is False
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in gh["missing_env"]

    # Instant + mock-backed tiles need nothing -> ready.
    assert tiles["ask"]["connector_ready"] is True
    assert tiles["inbox-summary"]["connector_ready"] is True

    # Set the token -> ready, no missing env.
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_x")
    gh2 = {t["id"]: t for t in client.get("/api/tiles").json()}["github-triage"]
    assert gh2["connector_ready"] is True and gh2["missing_env"] == []


def test_list_connectors_endpoint():
    client, _ = _client()
    conns = {c["id"]: c for c in client.get("/api/connectors").json()}
    assert "gmail" in conns and conns["gmail"]["kind"] == "mock"
    assert any(t["name"] == "send_message" and t["side_effect"] for t in conns["gmail"]["tools"])


def _tmp_client(tmp_path):
    """A board rooted in a temp dir (with one mock connector) so create writes there."""
    conn = tmp_path / "connectors" / "app"
    conn.mkdir(parents=True)
    (conn / "manifest.yaml").write_text(
        "id: app\napp: App\nkind: mock\ntools:\n"
        "  - {name: read_thing, description: r, side_effect: false}\n"
        "  - {name: do_thing, description: d, side_effect: true}\n",
        encoding="utf-8",
    )
    (conn / "adapter.py").write_text(
        "from tiles_ai.connectors import MockConnector\n\n\nclass A(MockConnector):\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tiles").mkdir(exist_ok=True)
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="c", provider="anthropic", api_key="k", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=tmp_path,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
    )
    return TestClient(app), tmp_path


def test_create_instant_tile_from_board(tmp_path):
    client, root = _tmp_client(tmp_path)
    resp = client.post("/api/tiles", json={"name": "My Helper", "instructions": "Help me."})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "my-helper" and body["connector"] is None
    # it now shows on the board (registry rescanned) and exists on disk
    assert "my-helper" in {t["id"] for t in client.get("/api/tiles").json()}
    assert (root / "tiles" / "my-helper" / "handler.py").is_file()


def test_create_connected_tile_from_board(tmp_path):
    client, _ = _tmp_client(tmp_path)
    resp = client.post(
        "/api/tiles",
        json={
            "name": "Reader",
            "connector": "app",
            "allowed_tools": ["read_thing"],
            "permission_tier": "read_only",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["connector"] == "app"


def test_create_tile_rejects_readonly_with_side_effect_tool(tmp_path):
    client, _ = _tmp_client(tmp_path)
    resp = client.post(
        "/api/tiles",
        json={
            "name": "Bad",
            "connector": "app",
            "allowed_tools": ["do_thing"],
            "permission_tier": "read_only",
        },
    )
    assert resp.status_code == 400
    assert "side-effect" in resp.json()["detail"].lower()


def test_create_tile_rejects_unknown_connector(tmp_path):
    client, _ = _tmp_client(tmp_path)
    resp = client.post("/api/tiles", json={"name": "X", "connector": "ghost"})
    assert resp.status_code == 400


def test_create_tile_rejects_duplicate(tmp_path):
    client, _ = _tmp_client(tmp_path)
    assert client.post("/api/tiles", json={"name": "Dup"}).status_code == 201
    assert client.post("/api/tiles", json={"name": "Dup"}).status_code == 400


def test_introspect_mcp_server_returns_tools(tmp_path):
    client, _ = _tmp_client(tmp_path)
    resp = client.post(
        "/api/connectors/introspect",
        json={"endpoint": f"{sys.executable} {SERVER} {tmp_path}"},
    )
    assert resp.status_code == 200
    tools = {t["name"]: t for t in resp.json()}
    assert "list_dir" in tools and tools["list_dir"]["side_effect"] is False
    assert tools["move_file"]["side_effect"] is True  # from readOnlyHint=false


def test_create_connector_then_tile_on_it(tmp_path):
    client, root = _tmp_client(tmp_path)
    # Connect a new app (mcp), then a tile that binds it — all from the API.
    created = client.post(
        "/api/connectors",
        json={
            "app": "Notes",
            "kind": "mcp",
            "endpoint": "npx -y notes-mcp",
            "env": ["NOTES_TOKEN"],
            "tools": [{"name": "search", "description": "s", "side_effect": False}],
        },
    )
    assert created.status_code == 201 and created.json()["id"] == "notes"
    assert "notes" in {c["id"] for c in client.get("/api/connectors").json()}

    tile = client.post(
        "/api/tiles",
        json={"name": "Note Search", "connector": "notes", "allowed_tools": ["search"]},
    )
    assert tile.status_code == 201 and tile.json()["connector"] == "notes"
    assert (root / "connectors" / "notes" / "adapter.py").is_file()


def test_errors_endpoint_surfaces_broken_tiles(tmp_path):
    # A tile whose manifest is invalid -> registry records it -> /api/errors shows it.
    broken = tmp_path / "tiles" / "oops"
    broken.mkdir(parents=True)
    (broken / "manifest.yaml").write_text(
        "id: oops\nname: Oops\n", encoding="utf-8"
    )  # missing fields
    (broken / "handler.py").write_text("x = 1\n", encoding="utf-8")
    client, _ = _tmp_client(tmp_path)
    errors = client.get("/api/errors").json()
    assert any(e["source"] == "oops" for e in errors)


def test_reload_endpoint_picks_up_a_new_tile(tmp_path):
    client, root = _tmp_client(tmp_path)
    before = {t["id"] for t in client.get("/api/tiles").json()}
    # Write a new tile directly to disk, then reload.
    from tiles_ai.scaffold import scaffold_tile

    scaffold_tile(root, id="added-later", name="Added Later")
    assert "added-later" not in {t["id"] for t in client.get("/api/tiles").json()}  # not yet
    client.post("/api/reload")
    after = {t["id"] for t in client.get("/api/tiles").json()}
    assert "added-later" in after and "added-later" not in before


def test_edit_tile_from_board(tmp_path):
    client, _ = _tmp_client(tmp_path)
    client.post("/api/tiles", json={"name": "Helper", "instructions": "old"})
    resp = client.put(
        "/api/tiles/helper",
        json={"instructions": "new instructions", "permission_tier": "draft"},
    )
    assert resp.status_code == 200
    detail = client.get("/api/tiles/helper").json()
    assert detail["permission_tier"] == "draft"
    assert detail["instructions"] == "new instructions"


def test_edit_tile_rejects_invalid_tier(tmp_path):
    client, _ = _tmp_client(tmp_path)
    client.post("/api/tiles", json={"name": "Helper"})
    assert client.put("/api/tiles/helper", json={"permission_tier": "nope"}).status_code == 400


def test_remove_provider(tmp_path):
    client, _ = _tmp_client(tmp_path)  # default "c"
    client.post(
        "/api/providers",
        json={"provider": {"id": "extra", "kind": "local", "endpoint": "http://x", "model": "m"}},
    )
    after = client.delete("/api/providers/extra").json()
    assert "extra" not in {p["id"] for p in after}
    assert client.delete("/api/providers/ghost").status_code == 404


def test_edit_connector_from_board(tmp_path):
    client, _ = _tmp_client(tmp_path)  # has connector "app"
    resp = client.put("/api/connectors/app", json={"app": "Renamed App"})
    assert resp.status_code == 200 and resp.json()["app"] == "Renamed App"


def test_delete_connector_refused_when_bound(tmp_path):
    client, _ = _tmp_client(tmp_path)
    client.post(
        "/api/tiles",
        json={"name": "Bound", "connector": "app", "allowed_tools": ["read_thing"]},
    )
    resp = client.delete("/api/connectors/app")
    assert resp.status_code == 409 and "used by" in resp.json()["detail"]


def test_delete_connector_when_free(tmp_path):
    client, _ = _tmp_client(tmp_path)
    assert client.delete("/api/connectors/app").status_code == 200
    assert "app" not in {c["id"] for c in client.get("/api/connectors").json()}


def test_delete_tile_from_board(tmp_path):
    client, _ = _tmp_client(tmp_path)
    client.post("/api/tiles", json={"name": "Temp"})
    assert client.delete("/api/tiles/temp").status_code == 200
    assert "temp" not in {t["id"] for t in client.get("/api/tiles").json()}
    assert client.delete("/api/tiles/ghost").status_code == 404


def test_app_factory_builds_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TILES_ECHO", "1")
    monkeypatch.setenv("TILES_ROOT", str(tmp_path))
    from tiles_ai.api.factory import make_app

    app = make_app()
    assert app.title == "Tiles AI"


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
