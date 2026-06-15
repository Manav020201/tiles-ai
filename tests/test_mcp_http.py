"""The Streamable HTTP MCP transport, against an in-process stdlib HTTP server.

Proves MCPConnector works over remote/hosted MCP servers (not just local stdio)
with no external dependency — the fixture server speaks the protocol in-thread.
"""

import asyncio
import http.server
import json
import threading

import pytest

from tiles_ai.connectors import MCPConnector, MCPError, StreamableHttpMCPClient
from tiles_ai.contracts import AuthConfig, CallContext, ConnectorManifest

TOOLS = [
    {"name": "echo", "description": "echo", "annotations": {"readOnlyHint": True}},
    {"name": "write_thing", "description": "writes", "annotations": {"readOnlyHint": False}},
]


def _result_for(method: str, params: dict) -> dict:
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return {"content": [{"type": "text", "text": f"called {params.get('name')}"}]}
    return {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        message = json.loads(self.rfile.read(length)) if length else {}
        self.server.last_auth = self.headers.get("Authorization")  # type: ignore[attr-defined]
        req_id = message.get("id")
        if req_id is None:  # notification
            self.send_response(202)
            self.end_headers()
            return
        result = _result_for(message.get("method"), message.get("params", {}))
        body = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("mcp-session-id", "sess-1")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    srv.last_auth = None  # type: ignore[attr-defined]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/mcp"


def test_streamable_http_client():
    srv, url = _server()

    async def go():
        c = StreamableHttpMCPClient(url)
        await c.start()
        tools = await c.list_tools()
        res = await c.call_tool("echo", {"x": 1})
        await c.stop()
        return tools, res, c.session_id

    try:
        tools, res, sid = asyncio.run(go())
    finally:
        srv.shutdown()

    assert {t["name"] for t in tools} == {"echo", "write_thing"}
    assert res["content"][0]["text"] == "called echo"
    assert sid == "sess-1"  # captured from the initialize response header


def test_mcp_connector_over_http():
    srv, url = _server()
    manifest = ConnectorManifest.model_validate(
        {
            "id": "remote",
            "app": "Remote",
            "kind": "mcp",
            "endpoint": url,
            "tools": [{"name": "echo", "description": "e", "side_effect": False}],
        }
    )

    async def go():
        c = MCPConnector.from_manifest(manifest)
        await c.connect(AuthConfig())
        try:
            live = await c.live_tools()
            ctx = CallContext(tile_id="t", allowed_tools=["echo"])
            result = await c.call_tool("echo", {}, ctx)
            return live, result
        finally:
            await c.disconnect()

    try:
        live, result = asyncio.run(go())
    finally:
        srv.shutdown()

    assert {t.name: t.side_effect for t in live} == {"echo": False, "write_thing": True}
    assert result.ok and result.output == "called echo"


def test_http_bearer_token_from_env(monkeypatch):
    srv, url = _server()
    monkeypatch.setenv("REMOTE_TOKEN", "secret123")
    manifest = ConnectorManifest.model_validate(
        {
            "id": "remote",
            "app": "Remote",
            "kind": "mcp",
            "endpoint": url,
            "auth": {"scheme": "api_key", "env": ["REMOTE_TOKEN"]},
            "tools": [{"name": "echo", "description": "e", "side_effect": False}],
        }
    )

    async def go():
        c = MCPConnector.from_manifest(manifest)
        await c.connect(AuthConfig(env=["REMOTE_TOKEN"]))
        await c.disconnect()

    try:
        asyncio.run(go())
    finally:
        srv.shutdown()

    assert srv.last_auth == "Bearer secret123"  # type: ignore[attr-defined]


def test_http_unreachable_raises():
    async def go():
        await StreamableHttpMCPClient("http://127.0.0.1:1/mcp").start()

    with pytest.raises(MCPError):
        asyncio.run(go())
