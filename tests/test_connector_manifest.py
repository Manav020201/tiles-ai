import pytest
from pydantic import ValidationError

from tiles_ai.contracts import ConnectorKind, ConnectorManifest


def _mock_manifest(**overrides):
    base = dict(
        id="gmail",
        app="Gmail",
        kind="mock",
        tools=[
            {"name": "list_messages", "description": "List inbox", "side_effect": False},
            {"name": "send_message", "description": "Send an email", "side_effect": True},
        ],
    )
    base.update(overrides)
    return base


def test_valid_mock_connector():
    m = ConnectorManifest.model_validate(_mock_manifest())
    assert m.id == "gmail"
    assert m.kind is ConnectorKind.MOCK
    assert m.tool_names() == {"list_messages", "send_message"}
    assert m.get_tool("send_message").side_effect is True


def test_mcp_requires_endpoint():
    with pytest.raises(ValidationError) as exc:
        ConnectorManifest.model_validate(_mock_manifest(kind="mcp", endpoint=None))
    assert "endpoint" in str(exc.value)


def test_mcp_with_endpoint_ok():
    m = ConnectorManifest.model_validate(
        _mock_manifest(kind="mcp", endpoint="https://mcp.example.com")
    )
    assert m.kind is ConnectorKind.MCP


def test_duplicate_tool_names_rejected():
    with pytest.raises(ValidationError) as exc:
        ConnectorManifest.model_validate(
            _mock_manifest(
                tools=[
                    {"name": "x", "description": "a"},
                    {"name": "x", "description": "b"},
                ]
            )
        )
    assert "duplicate" in str(exc.value)


def test_bad_id_rejected():
    with pytest.raises(ValidationError):
        ConnectorManifest.model_validate(_mock_manifest(id="Gmail Connector!"))


def test_unknown_field_forbidden():
    with pytest.raises(ValidationError):
        ConnectorManifest.model_validate(_mock_manifest(typo_field="oops"))
