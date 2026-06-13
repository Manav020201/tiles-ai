"""Registry discovery + loading, exercised against real on-disk fixture boards."""

import textwrap
from pathlib import Path

from tiles_ai.contracts import Connector, Tile, TileState
from tiles_ai.registry import Registry

# --- fixture source for the loaded Python files ----------------------------

VALID_ADAPTER = textwrap.dedent(
    """
    from tiles_ai.contracts import Connector, Session, ToolResult

    class MockAdapter(Connector):
        async def connect(self, auth):
            return Session(connector_id=self.manifest_id)
        async def list_tools(self):
            return []
        async def call_tool(self, name, args, context):
            return ToolResult(ok=True, output=None)
    """
)

VALID_HANDLER = textwrap.dedent(
    """
    from tiles_ai.contracts import Tile, ActionPlan

    class MockHandler(Tile):
        async def run(self, input, context):
            return ActionPlan(result="ok")
    """
)


# --- fixture builders ------------------------------------------------------

def _connector(root: Path, *, folder=None, manifest=None, adapter=VALID_ADAPTER):
    folder = folder or "gmail"
    manifest = manifest or textwrap.dedent(
        """
        id: gmail
        app: Gmail
        kind: mock
        tools:
          - name: list_messages
            description: List
            side_effect: false
          - name: send_message
            description: Send
            side_effect: true
        """
    )
    d = root / "connectors" / folder
    d.mkdir(parents=True)
    (d / "manifest.yaml").write_text(manifest)
    if adapter is not None:
        (d / "adapter.py").write_text(adapter)
    return d


def _tile(root: Path, *, folder=None, manifest=None, handler=VALID_HANDLER):
    folder = folder or "inbox-summary"
    manifest = manifest or textwrap.dedent(
        """
        id: inbox-summary
        name: Inbox Summary
        description: Summarize unread mail
        connector: gmail
        instructions: Summarize.
        allowed_tools: [list_messages]
        permission_tier: read_only
        """
    )
    d = root / "tiles" / folder
    d.mkdir(parents=True)
    (d / "manifest.yaml").write_text(manifest)
    if handler is not None:
        (d / "handler.py").write_text(handler)
    return d


# --- tests -----------------------------------------------------------------

def test_empty_board_is_ok(tmp_path):
    reg = Registry.discover(tmp_path)
    assert reg.ok
    assert reg.connectors == {} and reg.tiles == {}


def test_valid_board_loads(tmp_path):
    _connector(tmp_path)
    _tile(tmp_path)
    reg = Registry.discover(tmp_path)
    assert reg.ok, reg.report()

    conn = reg.get_connector("gmail")
    assert conn is not None
    assert issubclass(conn.adapter_cls, Connector)

    tile = reg.get_tile("inbox-summary")
    assert tile is not None
    assert tile.state is TileState.AVAILABLE
    assert issubclass(tile.handler_cls, Tile)


def test_many_tiles_one_connector_fanout(tmp_path):
    _connector(tmp_path)
    _tile(tmp_path)  # read_only inbox-summary
    _tile(
        tmp_path,
        folder="reply-drafter",
        manifest=textwrap.dedent(
            """
            id: reply-drafter
            name: Reply Drafter
            description: Draft replies
            connector: gmail
            instructions: Draft.
            allowed_tools: [list_messages, send_message]
            permission_tier: draft
            """
        ),
    )
    reg = Registry.discover(tmp_path)
    assert reg.ok, reg.report()
    assert {t.id for t in reg.tiles_for_connector("gmail")} == {
        "inbox-summary",
        "reply-drafter",
    }


def test_tile_binding_missing_connector_rejected(tmp_path):
    # No connector created at all.
    _tile(tmp_path)
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert "inbox-summary" not in reg.tiles
    assert any("not found" in e for err in reg.errors for e in err.errors)


def test_tile_allowlisting_unknown_tool_rejected(tmp_path):
    _connector(tmp_path)
    _tile(
        tmp_path,
        manifest=textwrap.dedent(
            """
            id: inbox-summary
            name: Inbox Summary
            description: x
            connector: gmail
            instructions: x
            allowed_tools: [list_messages, nonexistent_tool]
            permission_tier: read_only
            """
        ),
    )
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert any("nonexistent_tool" in e for err in reg.errors for e in err.errors)


def test_read_only_tile_with_side_effect_tool_rejected(tmp_path):
    _connector(tmp_path)
    _tile(
        tmp_path,
        manifest=textwrap.dedent(
            """
            id: inbox-summary
            name: Inbox Summary
            description: x
            connector: gmail
            instructions: x
            allowed_tools: [send_message]
            permission_tier: read_only
            """
        ),
    )
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert any("side-effectful" in e for err in reg.errors for e in err.errors)


def test_adapter_with_no_connector_subclass_rejected(tmp_path):
    _connector(tmp_path, adapter="x = 1  # no Connector subclass here\n")
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert "gmail" not in reg.connectors
    assert any("no concrete Connector" in e for err in reg.errors for e in err.errors)


def test_handler_with_two_tile_subclasses_rejected(tmp_path):
    _connector(tmp_path)
    two = textwrap.dedent(
        """
        from tiles_ai.contracts import Tile, ActionPlan

        class A(Tile):
            async def run(self, input, context): return ActionPlan()
        class B(Tile):
            async def run(self, input, context): return ActionPlan()
        """
    )
    _tile(tmp_path, handler=two)
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert any("multiple Tile subclasses" in e for err in reg.errors for e in err.errors)


def test_folder_name_must_match_manifest_id(tmp_path):
    _connector(tmp_path, folder="not-gmail")  # manifest id is still 'gmail'
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert any("folder name" in e for err in reg.errors for e in err.errors)


def test_import_error_in_handler_is_reported_not_raised(tmp_path):
    _connector(tmp_path)
    _tile(tmp_path, handler="import this_module_does_not_exist\n")
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert "inbox-summary" not in reg.tiles
    assert any("error importing" in e for err in reg.errors for e in err.errors)


def test_invalid_manifest_reported_with_folder_name(tmp_path):
    _connector(tmp_path, manifest="id: gmail\napp: Gmail\nkind: mcp\n")  # mcp needs endpoint
    reg = Registry.discover(tmp_path)
    assert not reg.ok
    assert any(err.source == "gmail" for err in reg.errors)
