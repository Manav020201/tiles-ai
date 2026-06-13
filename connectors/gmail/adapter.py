"""Gmail connector adapter (v0 mock).

Subclasses the generic `MockConnector` and registers canned responses for each
tool. This is the whole adapter — copy this file, change the responses, and you
have a new mock connector. A real Gmail connector would instead implement
`connect`/`list_tools`/`call_tool` against Gmail's MCP server, leaving the tile
contract untouched.
"""

from __future__ import annotations

from tiles_ai.connectors import MockConnector

# A tiny fake inbox the mock returns for `list_messages`.
_FAKE_INBOX = [
    {"from": "ops@status.io", "subject": "Nightly build passed", "unread": True},
    {"from": "jane@team.com", "subject": "Re: launch checklist", "unread": True},
    {"from": "newsletter@py.dev", "subject": "This week in Python", "unread": False},
]


class GmailMock(MockConnector):
    def __init__(self, manifest):
        super().__init__(manifest)
        self.set_response("list_messages", _FAKE_INBOX)
        # Side-effectful: only ever reached via the permission gate on approval.
        self.set_response(
            "send_message",
            lambda args: {"status": "sent (mock)", "to": args.get("to")},
        )
