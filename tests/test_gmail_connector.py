"""Real Gmail connector: REST calls (against a fake HTTP layer), OAuth authorize
params, and token refresh-at-activate. The live Google calls can't run here, so
these exercise the request/response handling and the OAuth plumbing."""

import asyncio
import base64
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from tiles_ai.contracts import CallContext, OAuthConfig
from tiles_ai.events import EventBus
from tiles_ai.model import BrainStore, ModelAdapter
from tiles_ai.oauth import TokenStore, build_authorize_url
from tiles_ai.registry import Registry
from tiles_ai.runtime import Runtime

REPO = Path(__file__).resolve().parents[1]


def _gmail():
    lc = Registry.discover(REPO).get_connector("gmail-live")
    conn = lc.adapter_cls.from_manifest(lc.manifest)
    conn.access_token = "tok"
    return conn


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._p


def test_list_messages_reads_headers(monkeypatch):
    def fake(req, timeout=30):
        url = req.full_url
        if "/messages/" in url:  # per-message metadata fetch
            return _Resp(
                {
                    "snippet": "hi there",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "a@b.com"},
                            {"name": "Subject", "value": "Hey"},
                        ]
                    },
                }
            )
        return _Resp({"messages": [{"id": "1"}]})  # the list call

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    res = asyncio.run(_gmail().call_tool("list_messages", {}, CallContext(tile_id="t")))
    assert res.ok and res.side_effect is False
    assert res.output[0] == {
        "from": "a@b.com",
        "subject": "Hey",
        "snippet": "hi there",
        "unread": True,
    }


def test_send_message_builds_raw_and_sets_bearer(monkeypatch):
    captured = {}

    def fake(req, timeout=30):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        captured["body"] = req.data
        return _Resp({"id": "sent1"})

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    res = asyncio.run(
        _gmail().call_tool(
            "send_message",
            {"to": "x@y.com", "subject": "Hi", "body": "yo"},
            CallContext(tile_id="t"),
        )
    )
    assert res.ok and res.side_effect is True
    assert res.output == {"status": "sent", "to": "x@y.com", "id": "sent1"}
    assert captured["url"].endswith("/messages/send")
    assert captured["auth"] == "Bearer tok"
    raw = base64.urlsafe_b64decode(json.loads(captured["body"])["raw"])
    assert b"x@y.com" in raw and b"yo" in raw


def test_unauthorized_gives_a_clear_message(monkeypatch):
    def fake(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b'{"error":"x"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    res = asyncio.run(_gmail().call_tool("list_messages", {}, CallContext(tile_id="t")))
    assert not res.ok and "re-authorize" in res.error


def test_connect_without_token_refuses():
    conn = _gmail()
    conn.access_token = None
    try:
        asyncio.run(conn.connect(None))
        raise AssertionError("expected connect to refuse")
    except Exception as exc:  # GmailError
        assert "not authorized" in str(exc)


def test_update_connector_sets_client_id_and_keeps_oauth(tmp_path):
    # Setting the OAuth client id from the board must persist it AND preserve the
    # rest of the oauth block (env-save used to clobber the whole auth section).
    import yaml

    from tiles_ai.scaffold import update_connector

    folder = tmp_path / "connectors" / "gmail-live"
    folder.mkdir(parents=True)
    src = (REPO / "connectors" / "gmail-live" / "manifest.yaml").read_text()
    (folder / "manifest.yaml").write_text(src)
    (folder / "adapter.py").write_text("x = 1\n")  # not loaded here

    update_connector(
        tmp_path,
        "gmail-live",
        {"app": "Gmail (live)", "env": ["GOOGLE_CLIENT_SECRET"], "oauth_client_id": "my-id.apps"},
    )

    data = yaml.safe_load((folder / "manifest.yaml").read_text())
    assert data["auth"]["oauth"]["client_id"] == "my-id.apps"
    assert data["auth"]["scheme"] == "oauth2"  # NOT reset to api_key by the env save
    assert data["auth"]["oauth"]["token_url"].startswith("https://oauth2.googleapis.com")
    assert data["auth"]["env"] == ["GOOGLE_CLIENT_SECRET"]


def test_authorize_url_carries_offline_consent_params():
    cfg = OAuthConfig(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id="cid",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
    )
    url = build_authorize_url(cfg, "http://127.0.0.1:8000/api/oauth/callback", "st")
    assert "access_type=offline" in url and "prompt=consent" in url
    assert "client_id=cid" in url


def test_expired_token_is_refreshed_at_activate(tmp_path, monkeypatch):
    ts = TokenStore.load(tmp_path / "oauth.local.yaml")
    ts.set(
        "gmail-live", {"access_token": "old", "refresh_token": "r", "expires_at": time.time() - 10}
    )

    async def fake_refresh(oauth, *, refresh, client_secret):
        assert refresh == "r"
        return {"access_token": "fresh", "refresh_token": "r", "expires_at": time.time() + 3600}

    monkeypatch.setattr("tiles_ai.runtime.runtime.refresh_token", fake_refresh)

    reg = Registry.discover(REPO)
    rt = Runtime(reg, ModelAdapter(BrainStore()), events=EventBus(), token_store=ts)
    auth = reg.get_connector("gmail-live").manifest.auth
    token = asyncio.run(rt._fresh_access_token("gmail-live", auth))

    assert token == "fresh"
    assert ts.access_token("gmail-live") == "fresh"  # persisted
