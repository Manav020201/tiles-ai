import pytest
from pydantic import ValidationError

from tiles_ai.contracts import ModelRef, PermissionTier, TileManifest


def _tile(**overrides):
    base = dict(
        id="inbox-summary",
        name="Inbox Summary",
        description="Summarize unread mail",
        connector="gmail",
        instructions="Summarize the inbox.",
        allowed_tools=["list_messages"],
        permission_tier="read_only",
    )
    base.update(overrides)
    return base


def test_valid_tile():
    t = TileManifest.model_validate(_tile())
    assert t.id == "inbox-summary"
    assert t.permission_tier is PermissionTier.READ_ONLY
    assert t.uses_default_brain() is True  # no model pinned


def test_instant_tile_needs_no_connector():
    t = TileManifest.model_validate(
        dict(
            id="ask",
            name="Ask",
            description="Ask the model anything",
            instructions="Answer the user.",
            permission_tier="read_only",
        )
    )
    assert t.connector is None
    assert t.allowed_tools == []


def test_allowed_tools_require_connector():
    with pytest.raises(ValidationError) as exc:
        TileManifest.model_validate(
            dict(
                id="bad",
                name="Bad",
                description="x",
                instructions="x",
                permission_tier="read_only",
                allowed_tools=["send_message"],  # but no connector
            )
        )
    assert "connector" in str(exc.value)


def test_pinned_model_marks_non_default_brain():
    t = TileManifest.model_validate(
        _tile(model={"provider": "ollama", "model": "llama3", "endpoint": "http://localhost:11434"})
    )
    assert t.uses_default_brain() is False
    assert isinstance(t.model, ModelRef)


def test_model_ref_rejects_api_key():
    # ModelRef is secret-free by construction (extra=forbid).
    with pytest.raises(ValidationError):
        ModelRef.model_validate({"provider": "anthropic", "model": "x", "api_key": "sk-..."})


def test_duplicate_allowed_tools_rejected():
    with pytest.raises(ValidationError) as exc:
        TileManifest.model_validate(_tile(allowed_tools=["list_messages", "list_messages"]))
    assert "duplicate" in str(exc.value)
