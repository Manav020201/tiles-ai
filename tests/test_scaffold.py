"""Scaffolding new tiles — the shared logic behind `tiles new` and the board form."""

import pytest

from tiles_ai.registry import Registry
from tiles_ai.scaffold import (
    ScaffoldError,
    class_name,
    scaffold_connector,
    scaffold_tile,
    slugify,
)


def test_slugify():
    assert slugify("My Cool Tile!") == "my-cool-tile"
    assert slugify("   ") == "tile"


def test_class_name():
    assert class_name("my-tile") == "MyTile"
    assert class_name("ask") == "Ask"


def test_scaffold_instant_tile_loads(tmp_path):
    folder = scaffold_tile(tmp_path, id="my-ask", name="My Ask", instructions="Answer.")
    assert (folder / "manifest.yaml").is_file()
    assert "PromptTile" in (folder / "handler.py").read_text()
    reg = Registry.discover(tmp_path)
    assert reg.ok and "my-ask" in reg.tiles
    assert reg.tiles["my-ask"].manifest.connector is None


def test_scaffold_connected_tile_loads(tmp_path):
    conn = tmp_path / "connectors" / "app"
    conn.mkdir(parents=True)
    (conn / "manifest.yaml").write_text(
        "id: app\napp: App\nkind: mock\n"
        "tools:\n  - {name: read_thing, description: r, side_effect: false}\n",
        encoding="utf-8",
    )
    (conn / "adapter.py").write_text(
        "from tiles_ai.connectors import MockConnector\n\n\nclass A(MockConnector):\n    pass\n",
        encoding="utf-8",
    )
    scaffold_tile(
        tmp_path, id="reader", name="Reader", connector="app", allowed_tools=["read_thing"]
    )
    reg = Registry.discover(tmp_path)
    assert reg.ok, reg.report()
    assert reg.tiles["reader"].manifest.connector == "app"


def test_scaffold_rejects_bad_id(tmp_path):
    with pytest.raises(ScaffoldError):
        scaffold_tile(tmp_path, id="Bad Id!", name="x")


def test_scaffold_rejects_collision(tmp_path):
    scaffold_tile(tmp_path, id="dup", name="Dup")
    with pytest.raises(ScaffoldError, match="already exists"):
        scaffold_tile(tmp_path, id="dup", name="Dup")


def test_scaffold_rejects_invalid_manifest(tmp_path):
    with pytest.raises(ScaffoldError):
        scaffold_tile(tmp_path, id="bad", name="Bad", permission_tier="superpowers")
    # nothing written on failure
    assert not (tmp_path / "tiles" / "bad").exists()


def test_scaffold_mcp_connector_loads(tmp_path):
    scaffold_connector(
        tmp_path,
        id="myapp",
        app="My App",
        kind="mcp",
        endpoint="npx -y some-mcp-server",
        env=["MYAPP_TOKEN"],
        tools=[{"name": "do_read", "description": "r", "side_effect": False}],
    )
    folder = tmp_path / "connectors" / "myapp"
    assert "MCPConnector" in (folder / "adapter.py").read_text()
    reg = Registry.discover(tmp_path)
    assert reg.ok, reg.report()
    conn = reg.connectors["myapp"]
    assert conn.manifest.kind.value == "mcp"
    assert conn.manifest.auth.env == ["MYAPP_TOKEN"]


def test_scaffold_mock_connector_loads(tmp_path):
    scaffold_connector(
        tmp_path, id="fake", app="Fake", kind="mock", tools=[{"name": "x", "side_effect": False}]
    )
    assert "MockConnector" in (tmp_path / "connectors" / "fake" / "adapter.py").read_text()
    assert Registry.discover(tmp_path).ok


def test_scaffold_connector_requires_endpoint_for_mcp(tmp_path):
    with pytest.raises(ScaffoldError, match="endpoint"):
        scaffold_connector(tmp_path, id="x", app="X", kind="mcp")
