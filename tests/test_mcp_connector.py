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


def test_reads_a_file_larger_than_64kb(tmp_path):
    # Regression: a JSON-RPC response over asyncio's default 64 KB readline limit
    # used to crash the stdio client (LimitOverrunError). A big file must read fine.
    big = "x" * 90_000  # > 64 KB; the server caps reads at 100 KB
    (tmp_path / "big.txt").write_text(big, encoding="utf-8")

    async def go():
        c = MCPConnector.from_manifest(_manifest(tmp_path))
        await c.connect(AuthConfig())
        try:
            return await c.call_tool("read_file", {"path": "big.txt"}, _ctx())
        finally:
            await c.disconnect()

    read = asyncio.run(go())
    assert read.ok and len(read.output) >= 64_000


def _full_manifest(root: Path) -> ConnectorManifest:
    return ConnectorManifest.model_validate(
        {
            "id": "local-files",
            "app": "Local files",
            "kind": "mcp",
            "endpoint": f"{sys.executable} {SERVER} {root}",
            "tools": [
                {"name": "list_dir", "description": "l", "side_effect": False},
                {"name": "read_file", "description": "r", "side_effect": False},
                {"name": "find_files", "description": "f", "side_effect": False},
                {"name": "move_file", "description": "m", "side_effect": True},
            ],
        }
    )


def test_find_files_and_move_file(tmp_path):
    (tmp_path / "report.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "skip.log").write_text("x", encoding="utf-8")

    async def go():
        c = MCPConnector.from_manifest(_full_manifest(tmp_path))
        await c.connect(AuthConfig())
        try:
            found = await c.call_tool("find_files", {"query": "report"}, _ctx())
            moved = await c.call_tool(
                "move_file", {"src": "report.txt", "dst": "txt/report.txt"}, _ctx()
            )
            return found, moved
        finally:
            await c.disconnect()

    found, moved = asyncio.run(go())
    assert found.ok and "report.txt" in found.output and "skip.log" not in found.output
    assert moved.ok and moved.side_effect is True  # manifest declares it side-effectful
    # The move actually happened on disk and created the parent dir.
    assert (tmp_path / "txt" / "report.txt").is_file()
    assert not (tmp_path / "report.txt").exists()


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


def _manifest_with_env(root: Path) -> ConnectorManifest:
    return ConnectorManifest.model_validate(
        {
            "id": "local-files",
            "app": "Local files",
            "kind": "mcp",
            "endpoint": f"{sys.executable} {SERVER} {root}",
            "auth": {"scheme": "api_key", "env": ["FILES_USER"]},
            "tools": [{"name": "whoami", "description": "who", "side_effect": False}],
        }
    )


def test_connect_fails_fast_when_required_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("FILES_USER", raising=False)

    async def go():
        c = MCPConnector.from_manifest(_manifest_with_env(tmp_path))
        await c.connect(AuthConfig(env=["FILES_USER"]))

    with pytest.raises(Exception) as exc:  # MCPError
        asyncio.run(go())
    assert "FILES_USER" in str(exc.value)


def test_env_is_passed_through_to_the_server(tmp_path, monkeypatch):
    monkeypatch.setenv("FILES_USER", "ada")

    async def go():
        c = MCPConnector.from_manifest(_manifest_with_env(tmp_path))
        await c.connect(AuthConfig(env=["FILES_USER"]))
        try:
            return await c.call_tool("whoami", {}, _ctx())
        finally:
            await c.disconnect()

    result = asyncio.run(go())
    assert result.ok and result.output == "ada"


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


@pytest.mark.skipif(shutil.which("python3") is None, reason="needs python3 on PATH")
def test_tidy_folder_draft_loop_moves_files_on_approval(tmp_path):
    # The full local "smart PC" draft loop: activate the Tidy Folder tile against a
    # real MCP server, propose moves, approve them, and confirm files actually move
    # on disk. Builds a temp board so we never mutate the repo's sample_docs.
    board = tmp_path / "board"
    shutil.copytree(REPO_ROOT / "connectors" / "local-files", board / "connectors" / "local-files")
    shutil.copytree(REPO_ROOT / "tiles" / "tidy-folder", board / "tiles" / "tidy-folder")

    content = tmp_path / "stuff"
    content.mkdir()
    (content / "a.txt").write_text("x", encoding="utf-8")
    (content / "b.log").write_text("y", encoding="utf-8")

    manifest = board / "connectors" / "local-files" / "manifest.yaml"
    manifest.write_text(
        manifest.read_text().replace(
            "python3 examples/mcp_servers/files_server.py sample_docs",
            f"{sys.executable} {SERVER} {content}",
        ),
        encoding="utf-8",
    )

    store = BrainStore()
    store.add_provider(
        HostedProvider(id="c", provider="anthropic", api_key="k", model="m"), make_default=True
    )
    reg = Registry.discover(board)
    assert reg.ok, reg.report()
    rt = Runtime(reg, ModelAdapter(store, client_factory=echo_client_factory))

    async def go():
        await rt.activate("tidy-folder")
        try:
            outcome = await rt.run("tidy-folder", ".")
            assert len(outcome.gate.queued) == 2  # two files -> two proposed moves
            assert not outcome.gate.executed  # draft tier: nothing fired yet
            for item in list(rt.pending_approvals("tidy-folder")):
                await rt.resolve_approval(item.id, True)
        finally:
            await rt.deactivate("tidy-folder")

    asyncio.run(go())
    # The approved moves actually happened, parent dirs created by type.
    assert (content / "txt" / "a.txt").is_file()
    assert (content / "log" / "b.log").is_file()
    assert not (content / "a.txt").exists()
