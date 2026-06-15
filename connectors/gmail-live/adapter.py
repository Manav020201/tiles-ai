"""Gmail (live) connector — a REAL connector over the Gmail REST API.

Auth is the board's OAuth flow: the user authorizes Gmail (🔌 → ⚙ → Authorize),
the token is stored locally, and the runtime injects it here as ``access_token``.
This adapter calls the Gmail REST API directly with that bearer (stdlib only, no
third-party server) and exposes the same two tools the mock does, so a tile's
handler is identical whether bound to the mock ``gmail`` or this real connector:

  * list_messages  — read recent unread mail (read-only)
  * send_message   — send an email (side-effectful → gated behind approval)

Setup (one-time, on Google's side — see docs/GMAIL.md): create an OAuth client in
Google Cloud, enable the Gmail API, then set the client id + secret on the
connector and click Authorize.

NOTE: the live Gmail calls were not exercised against a real account during
development (no credentials available). The request/response shapes follow the
Gmail v1 API; adjust here if Google changes a field.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

from tiles_ai.contracts import AuthConfig, CallContext, Connector, Session, ToolResult

API = "https://gmail.googleapis.com/gmail/v1/users/me"
_MAX_MESSAGES = 10


class GmailError(Exception):
    """A Gmail API call failed."""


class GmailConnector(Connector):
    """Real Gmail connector. Uses the OAuth access token injected by the runtime."""

    def __init__(self, manifest) -> None:
        super().__init__(manifest.id)
        self.manifest = manifest
        # Set by the runtime from the OAuth token store before connect().
        self.access_token: str | None = None

    @classmethod
    def from_manifest(cls, manifest) -> GmailConnector:
        return cls(manifest)

    async def connect(self, auth: AuthConfig) -> Session:
        if not self.access_token:
            raise GmailError(
                f"connector '{self.manifest_id}' is not authorized — connect Gmail "
                "from the board (🔌 → ⚙ → Authorize) first."
            )
        return Session(connector_id=self.manifest_id)

    async def list_tools(self):
        return list(self.manifest.tools)

    async def call_tool(self, name: str, args: dict, context: CallContext) -> ToolResult:
        try:
            if name == "list_messages":
                return ToolResult(ok=True, output=self._list_messages(), side_effect=False)
            if name == "send_message":
                return ToolResult(ok=True, output=self._send_message(args or {}), side_effect=True)
            return ToolResult(ok=False, error=f"unknown tool '{name}'", side_effect=False)
        except GmailError as exc:
            # side_effect echoes the tool's declared flag even on failure.
            return ToolResult(ok=False, error=str(exc), side_effect=name == "send_message")

    # --- Gmail REST ---------------------------------------------------------

    def _list_messages(self) -> list[dict]:
        listing = self._api(
            "GET", "/messages", params={"q": "is:unread", "maxResults": _MAX_MESSAGES}
        )
        out: list[dict] = []
        for ref in (listing.get("messages") or [])[:_MAX_MESSAGES]:
            msg = self._api(
                "GET",
                f"/messages/{ref['id']}",
                params=[
                    ("format", "metadata"),
                    ("metadataHeaders", "From"),
                    ("metadataHeaders", "Subject"),
                ],
            )
            headers = {
                h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }
            out.append(
                {
                    "from": headers.get("from", ""),
                    "subject": headers.get("subject", "(no subject)"),
                    "snippet": msg.get("snippet", ""),
                    "unread": True,
                }
            )
        return out

    def _send_message(self, args: dict) -> dict:
        to = args.get("to")
        if not to:
            raise GmailError("send_message needs a 'to' address")
        mime = EmailMessage()
        mime["To"] = to
        mime["Subject"] = args.get("subject", "")
        mime.set_content(args.get("body", ""))
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        sent = self._api("POST", "/messages/send", body={"raw": raw})
        return {"status": "sent", "to": to, "id": sent.get("id")}

    def _api(self, method: str, path: str, *, params=None, body=None) -> dict:
        url = f"{API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("authorization", f"Bearer {self.access_token}")
        if body is not None:
            req.add_header("content-type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
                return json.loads(payload.decode("utf-8")) if payload else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code in (401, 403):
                raise GmailError(
                    "Gmail rejected the request (auth expired or scope missing) — "
                    "re-authorize from the board. Details: " + detail
                ) from exc
            raise GmailError(f"Gmail API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GmailError(f"could not reach Gmail: {exc.reason}") from exc
