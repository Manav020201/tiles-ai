"""OAuth 2.0 (authorization-code) — token store + flow helpers.

The board runs the flow: build an authorize URL → the provider redirects back to
our callback with a `code` → we exchange it at the token endpoint → store the
access token locally, keyed by connector id. At connect time the connector uses
the stored token as its bearer.

Tokens are secrets: they live only in `oauth.local.yaml` (gitignored), never in
a manifest. Manifests carry only the OAuth *config* (URLs, client id, scopes).

This is a standard, provider-agnostic authorization-code implementation. It can't
be exercised end-to-end without a real provider, so the tests drive it against a
fake in-process token server.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from .contracts import OAuthConfig


class OAuthError(Exception):
    """An OAuth flow step failed."""


def build_authorize_url(oauth: OAuthConfig, redirect_uri: str, state: str) -> str:
    """The provider authorize URL to send the user to."""
    params = {
        "response_type": "code",
        "client_id": oauth.client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if oauth.scopes:
        params["scope"] = " ".join(oauth.scopes)
    sep = "&" if "?" in oauth.authorize_url else "?"
    return f"{oauth.authorize_url}{sep}{urllib.parse.urlencode(params)}"


async def exchange_code(
    oauth: OAuthConfig, *, code: str, redirect_uri: str, client_secret: str | None
) -> dict:
    """Exchange an authorization code for a token at the token endpoint."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": oauth.client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    raw = await asyncio.to_thread(_post_form, oauth.token_url, data)
    return _to_token(raw)


async def refresh_token(oauth: OAuthConfig, *, refresh: str, client_secret: str | None) -> dict:
    """Exchange a refresh token for a fresh access token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": oauth.client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    raw = await asyncio.to_thread(_post_form, oauth.token_url, data)
    token = _to_token(raw)
    token.setdefault("refresh_token", refresh)  # providers may omit it on refresh
    return token


def _to_token(raw: dict) -> dict:
    if "access_token" not in raw:
        raise OAuthError(f"token response missing access_token: {raw}")
    expires_in = raw.get("expires_in")
    return {
        "access_token": raw["access_token"],
        "refresh_token": raw.get("refresh_token"),
        "token_type": raw.get("token_type", "Bearer"),
        "expires_at": (time.time() + float(expires_in)) if expires_in else None,
    }


def _post_form(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("content-type", "application/x-www-form-urlencoded")
    req.add_header("accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise OAuthError(
            f"HTTP {exc.code} from {url}: {exc.read().decode('utf-8', 'replace')}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OAuthError(f"could not reach {url}: {exc.reason}") from exc


class TokenStore:
    """Per-machine OAuth token store (gitignored YAML). Connector id -> token."""

    def __init__(self, tokens: dict | None = None, *, path: str | Path | None = None):
        self._tokens: dict[str, dict] = tokens or {}
        self._path = Path(path) if path else None

    @classmethod
    def load(cls, path: str | Path) -> TokenStore:
        p = Path(path)
        if not p.exists():
            return cls({}, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls(data, path=p)

    def set(self, connector_id: str, token: dict) -> None:
        self._tokens[connector_id] = token
        self._save()

    def remove(self, connector_id: str) -> None:
        self._tokens.pop(connector_id, None)
        self._save()

    def get(self, connector_id: str) -> dict | None:
        return self._tokens.get(connector_id)

    def access_token(self, connector_id: str) -> str | None:
        token = self._tokens.get(connector_id)
        return token.get("access_token") if token else None

    def is_authorized(self, connector_id: str) -> bool:
        return connector_id in self._tokens

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(yaml.safe_dump(self._tokens, sort_keys=False), encoding="utf-8")
