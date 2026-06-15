"""Real OAuth (authorization-code) — token store + flow against a fake provider."""

import asyncio
import http.server
import json
import threading
import urllib.parse
from pathlib import Path

from fastapi.testclient import TestClient

from tiles_ai.api import create_app
from tiles_ai.connectors import MCPConnector
from tiles_ai.contracts import AuthConfig, ConnectorManifest, OAuthConfig
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory
from tiles_ai.oauth import TokenStore, build_authorize_url, exchange_code

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_authorize_url():
    oauth = OAuthConfig(
        authorize_url="https://prov/auth",
        token_url="https://prov/token",
        client_id="abc",
        scopes=["read", "write"],
    )
    url = build_authorize_url(oauth, "http://localhost:8000/api/oauth/callback", "xyz")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["client_id"] == ["abc"]
    assert q["state"] == ["xyz"]
    assert q["scope"] == ["read write"]
    assert q["redirect_uri"] == ["http://localhost:8000/api/oauth/callback"]
    assert q["response_type"] == ["code"]


def test_token_store_roundtrip(tmp_path):
    path = tmp_path / "oauth.local.yaml"
    store = TokenStore(path=path)
    store.set("github", {"access_token": "tok-1", "refresh_token": "r"})
    assert store.access_token("github") == "tok-1"
    assert store.is_authorized("github")
    assert TokenStore.load(path).access_token("github") == "tok-1"
    store.remove("github")
    assert not store.is_authorized("github")


# --- fake OAuth token endpoint --------------------------------------------


class _TokenHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        self.server.last_form = {k: v[0] for k, v in form.items()}  # type: ignore[attr-defined]
        body = json.dumps(
            {"access_token": "ACCESS-123", "refresh_token": "REFRESH-9", "expires_in": 3600}
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _token_server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _TokenHandler)
    srv.last_form = None  # type: ignore[attr-defined]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/token"


def test_exchange_code_against_fake_provider():
    srv, token_url = _token_server()
    oauth = OAuthConfig(authorize_url="https://x/auth", token_url=token_url, client_id="cid")

    async def go():
        return await exchange_code(
            oauth, code="the-code", redirect_uri="http://cb", client_secret="sek"
        )

    try:
        token = asyncio.run(go())
    finally:
        srv.shutdown()

    assert token["access_token"] == "ACCESS-123"
    assert token["refresh_token"] == "REFRESH-9"
    assert token["expires_at"] is not None
    assert srv.last_form["grant_type"] == "authorization_code"  # type: ignore[attr-defined]
    assert srv.last_form["code"] == "the-code"  # type: ignore[attr-defined]
    assert srv.last_form["client_secret"] == "sek"  # type: ignore[attr-defined]


def test_oauth_flow_endpoints_store_token(tmp_path):
    # A board with an OAuth connector pointing at the fake token server.
    srv, token_url = _token_server()
    conn = tmp_path / "connectors" / "svc"
    conn.mkdir(parents=True)
    (conn / "manifest.yaml").write_text(
        "id: svc\napp: Service\nkind: mcp\nendpoint: https://svc.example/mcp\n"
        "auth:\n  scheme: oauth2\n  oauth:\n"
        f"    authorize_url: https://svc.example/auth\n    token_url: {token_url}\n"
        "    client_id: my-client\n"
        "tools:\n  - {name: ping, description: p, side_effect: false}\n",
        encoding="utf-8",
    )
    (conn / "adapter.py").write_text(
        "from tiles_ai.connectors import MCPConnector\n\n\nclass S(MCPConnector):\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tiles").mkdir()
    store = BrainStore()
    app = create_app(
        root=tmp_path,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
        token_store=TokenStore(path=tmp_path / "oauth.local.yaml"),
    )
    client = TestClient(app)

    # Connector view reports it's an OAuth connector, not yet authorized.
    view = {c["id"]: c for c in client.get("/api/connectors").json()}["svc"]
    assert view["oauth"] is True and view["authorized"] is False

    # Start -> get an authorize URL carrying a state.
    start = client.get("/api/connectors/svc/oauth/start").json()
    state = urllib.parse.parse_qs(urllib.parse.urlparse(start["authorize_url"]).query)["state"][0]

    # Simulate the provider redirect back to our callback with a code.
    cb = client.get(f"/api/oauth/callback?code=abc&state={state}")
    assert cb.status_code == 200 and "Connected" in cb.text

    # Token is stored; the connector now reports authorized.
    view2 = {c["id"]: c for c in client.get("/api/connectors").json()}["svc"]
    assert view2["authorized"] is True

    # Disconnect clears it.
    after = client.post("/api/connectors/svc/oauth/disconnect").json()
    assert after["authorized"] is False
    srv.shutdown()


def test_runtime_uses_oauth_token_as_bearer(tmp_path):
    # The runtime injects the stored token; an OAuth connector with no token refuses.
    manifest = ConnectorManifest.model_validate(
        {
            "id": "svc",
            "app": "Svc",
            "kind": "mcp",
            "endpoint": "https://svc.example/mcp",
            "auth": {
                "scheme": "oauth2",
                "oauth": {
                    "authorize_url": "https://x/a",
                    "token_url": "https://x/t",
                    "client_id": "c",
                },
            },
            "tools": [{"name": "ping", "description": "p", "side_effect": False}],
        }
    )

    async def go():
        c = MCPConnector.from_manifest(manifest)
        # No token set -> OAuth connector refuses to connect.
        try:
            await c.connect(AuthConfig(scheme="oauth2", oauth=manifest.auth.oauth))
        except Exception as exc:
            return str(exc)
        return "connected unexpectedly"

    assert "OAuth authorization" in asyncio.run(go())
