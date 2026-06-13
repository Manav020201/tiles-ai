"""Manifests load from real YAML files exactly as authored on disk."""

import textwrap

from tiles_ai.contracts import (
    ConnectorKind,
    load_connector_manifest,
    load_tile_manifest,
)


def test_load_connector_yaml(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text(
        textwrap.dedent(
            """
            id: gmail
            app: Gmail
            kind: mock
            auth:
              scheme: api_key
              scopes: [read, send]
            tools:
              - name: list_messages
                description: List inbox messages
                side_effect: false
              - name: send_message
                description: Send an email
                side_effect: true
            """
        ),
        encoding="utf-8",
    )
    m = load_connector_manifest(path)
    assert m.id == "gmail"
    assert m.kind is ConnectorKind.MOCK
    assert m.auth.scopes == ["read", "send"]
    assert m.get_tool("send_message").side_effect is True


def test_load_tile_yaml(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text(
        textwrap.dedent(
            """
            id: inbox-summary
            name: Inbox Summary
            description: Summarize unread mail
            icon: "📥"
            connector: gmail
            instructions: Summarize the inbox in three bullets.
            allowed_tools: [list_messages]
            permission_tier: read_only
            provides:
              - name: email.summary
                description: A short summary of the inbox
            """
        ),
        encoding="utf-8",
    )
    t = load_tile_manifest(path)
    assert t.id == "inbox-summary"
    assert t.uses_default_brain() is True
    assert t.provides[0].name == "email.summary"
