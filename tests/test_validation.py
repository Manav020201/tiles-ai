"""Cross-manifest validation — the 'connector + allowed_tools resolve' rule."""

import pytest

from tiles_ai.contracts import (
    ConnectorManifest,
    ContractError,
    TileManifest,
    assert_tile_valid,
    validate_tile_against_connector,
)


def _connector():
    return ConnectorManifest.model_validate(
        {
            "id": "gmail",
            "app": "Gmail",
            "kind": "mock",
            "tools": [
                {"name": "list_messages", "description": "List", "side_effect": False},
                {"name": "send_message", "description": "Send", "side_effect": True},
            ],
        }
    )


def _tile(**overrides):
    base = dict(
        id="inbox-summary",
        name="Inbox Summary",
        description="x",
        connector="gmail",
        instructions="x",
        allowed_tools=["list_messages"],
        permission_tier="read_only",
    )
    base.update(overrides)
    return TileManifest.model_validate(base)


def test_valid_pairing_has_no_errors():
    assert validate_tile_against_connector(_tile(), _connector()) == []


def test_missing_connector_flagged():
    errors = validate_tile_against_connector(_tile(), None)
    assert any("not found" in e for e in errors)


def test_unknown_allowed_tool_flagged():
    tile = _tile(allowed_tools=["list_messages", "delete_everything"])
    errors = validate_tile_against_connector(tile, _connector())
    assert any("delete_everything" in e for e in errors)


def test_read_only_cannot_allowlist_side_effect_tool():
    tile = _tile(allowed_tools=["send_message"], permission_tier="read_only")
    errors = validate_tile_against_connector(tile, _connector())
    assert any("side-effectful" in e for e in errors)


def test_draft_may_allowlist_side_effect_tool():
    tile = _tile(allowed_tools=["send_message"], permission_tier="draft")
    assert validate_tile_against_connector(tile, _connector()) == []


def test_instant_tile_resolves_with_no_connector():
    tile = TileManifest.model_validate(
        {
            "id": "ask",
            "name": "Ask",
            "description": "x",
            "instructions": "x",
            "permission_tier": "read_only",
        }
    )
    assert validate_tile_against_connector(tile, None) == []


def test_assert_raises_on_invalid():
    tile = _tile(allowed_tools=["nope"])
    with pytest.raises(ContractError):
        assert_tile_valid(tile, _connector())
