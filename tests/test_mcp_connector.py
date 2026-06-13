"""The real MCP connector, exercised against the bundled example stdio server."""

import asyncio
import shutil
import sys
from pathlib import Path

import pytest

from tiles_ai.connectors import MCPConnector
from tiles_ai.contracts import AuthConfig, CallContext, ConnectorManifest, HostedProvider
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory
from tiles_ai.registry import Registry
from tiles_ai.runtime import Runtime

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER = REPO_ROOT / "examples" / "mcp_servers" / "files_server.py"


def _manifest(root: Path) -> ConnectorManifest:
    return ConnectorManifest.model_validate(
        {
            "id": "local-files",
            "app": "Local files",
            "kind": "mcp",
            "endpoint": f"{sys.executable} {SERVER} {root}",
            "tools": [
                {"name": "list_dir", "description": "list", "side_effect": False},
                {"name": "read_file", "description": "read", "side_effect": False},
            ],
        }
    )


def _ctx():
    return CallContext(tile_id="t", allowed_tools=["list_dir", "read_file"])


def test_connector_lists_and_reads(tmp_path):
    (tmp_path / "note.txt").write_text("the answer is 42", encoding="utf-8")

    async def go():
        c = MCPConnector.from_manifest(_manifest(tmp_path))
        await c.connect(AuthConfig())
        try:
            listing = await c.call_tool("list_dir", {"path": "."}, _ctx())
            read = await c.call_tool("read_file", {"path": "note.txt"}, _ctx())
            return listing, read
        finally:
            await c.disconnect()

    listing, read = asyncio.run(go())
    assert listing.ok and "note.txt" in listing.output
    assert read.ok and read.output == "the answer is 42"
    assert read.side_effect is False  # manifest is the authority


def test_connector_refuses_path_traversal(tmp_path):
    async def go():
        c = MCPConnector.from_manifest(_manifest(tmp_path))
        await c.connect(AuthConfig())
        try:
            return await c.call_tool("read_file", {"path": "../../etc/hosts"}, _ctx())
        finally:
            await c.disconnect()

    result = asyncio.run(go())
    assert result.ok is False
    assert "escapes the root" in result.error


def test_live_tools_derive_side_effect_from_readonly_hint(tmp_path):
    async def go():
        c = MCPConnector.from_manifest(_manifest(tmp_path))
        await c.connect(AuthConfig())
        try:
            return await c.live_tools()
        finally:
            await c.disconnect()

    tools = {t.name: t for t in asyncio.run(go())}
    assert tools["list_dir"].side_effect is False  # readOnlyHint -> not a side effect
    assert tools["read_file"].side_effect is False


def test_unknown_tool_is_reported(tmp_path):
    async def go():
        c = MCPConnector.from_manifest(_manifest(tmp_path))
        await c.connect(AuthConfig())
        try:
            return await c.call_tool("nope", {}, _ctx())
        finally:
            await c.disconnect()

    result = asyncio.run(go())
    assert result.ok is False and "no tool 'nope'" in result.error


def test_registry_loads_mcp_connector_and_tile():
    reg = Registry.discover(REPO_ROOT)
    assert reg.ok, reg.report()
    conn = reg.get_connector("local-files")
    assert conn is not None and conn.manifest.kind.value == "mcp"
    tile = reg.get_tile("ask-my-files")
    assert tile is not None
    assert tile.manifest.connector == "local-files"
    assert tile.manifest.permission_tier.value == "read_only"


@pytest.mark.skipif(shutil.which("python3") is None, reason="needs python3 on PATH")
def test_runtime_reads_files_through_mcp_end_to_end():
    # Uses the committed connector (endpoint launches the example server relative
    # to the repo root); pytest runs from there.
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="cloud", provider="anthropic", api_key="sk", model="claude-opus-4-8"),
        make_default=True,
    )
    reg = Registry.discover(REPO_ROOT)
    rt = Runtime(reg, ModelAdapter(store, client_factory=echo_client_factory))

    async def go():
        active = await rt.activate("ask-my-files")
        try:
            # Read through the runtime's ToolProxy -> live MCP subprocess.
            listing = await active.context.tools.call("list_dir", {"path": "."})
            outcome = await rt.run("ask-my-files", "What's in my docs?")
            return listing, outcome
        finally:
            await rt.deactivate("ask-my-files")

    listing, outcome = asyncio.run(go())
    assert listing.ok and "project-notes.md" in listing.output
    assert outcome.result.startswith("[echo:")  # answered with the default brain
    assert not outcome.gate.queued and not outcome.gate.rejected
