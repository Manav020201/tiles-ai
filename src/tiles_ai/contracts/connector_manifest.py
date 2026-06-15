"""Connector manifest schema.

A *connector* is the durable, reusable connection to one application: its auth
and its tool surface. One connector per app. Many tiles can bind to the same
connector (a read-only "summarize inbox" tile and a "draft replies" tile both
bind to one Gmail connector). The heavy, slow-changing thing is the app
connection — not the agent's prompt — so it lives here, separately.

In the general case a connector is a binding to an app's MCP server. v0 ships a
`mock` connector; this schema is shaped so a real `mcp`-backed connector drops
in unchanged.

This module defines the on-disk shape of `connectors/<id>/manifest.yaml`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ids import SLUG_PATTERN


class ConnectorKind(str, Enum):
    """How a connector talks to its application."""

    MCP = "mcp"
    """Binds to the app's MCP server (the general case; wired in a later phase)."""

    MOCK = "mock"
    """Fakes the tool surface in-process. The v0 default for reference tiles."""

    CUSTOM = "custom"
    """Hand-written adapter that is neither MCP nor a stock mock."""


class OAuthConfig(BaseModel):
    """OAuth 2.0 authorization-code config for a connector.

    Declared in the manifest (URLs, client id, scopes — not secrets). The client
    secret, if any, is read from `client_secret_env` (a local env var). The board
    runs the authorize → callback → token-exchange flow and stores the resulting
    access token locally (never in the manifest).
    """

    model_config = ConfigDict(extra="forbid")

    authorize_url: str = Field(description="The provider's authorization endpoint.")
    token_url: str = Field(description="The provider's token endpoint.")
    client_id: str = Field(description="OAuth client id (public).")
    client_secret_env: str | None = Field(
        default=None, description="Env var holding the client secret (local only)."
    )
    scopes: list[str] = Field(default_factory=list)


class AuthConfig(BaseModel):
    """Auth scheme + scopes for a connector.

    `env` names host env vars the server needs (passed through / bearer). `oauth`
    declares an OAuth 2.0 flow the board can run. Secrets never live here.
    """

    model_config = ConfigDict(extra="forbid")

    scheme: str = Field(
        default="none",
        description="Auth scheme, e.g. 'none', 'api_key', 'oauth2'.",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Permission scopes the connection requests from the app.",
    )
    oauth: OAuthConfig | None = Field(
        default=None, description="OAuth 2.0 config when scheme is 'oauth2'."
    )
    env: list[str] = Field(
        default_factory=list,
        description=(
            "Names (not values) of environment variables the connector's server "
            "requires, e.g. ['GITHUB_PERSONAL_ACCESS_TOKEN']. The MCP connector "
            "passes them through from the host environment to the launched server "
            "and fails fast if one is missing. Values never live in a manifest."
        ),
    )


class ToolSpec(BaseModel):
    """One tool the application exposes — the unit a tile is allow-listed to.

    The connector is the authority on `side_effect`: it declares whether
    invoking this tool touches the outside world. The permission gate trusts
    this flag, so getting it right here is a safety-critical responsibility of
    the connector author.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Tool name, unique within the connector.")
    description: str = Field(description="One line: what calling this tool does.")
    side_effect: bool = Field(
        default=False,
        description=(
            "True if invoking this tool causes a real-world side effect "
            "(send, post, write, delete). Drives the permission gate."
        ),
    )
    input_schema: dict | None = Field(
        default=None,
        description="Optional JSON Schema for the tool's arguments.",
    )

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("tool name must be non-empty")
        return v


class ConnectorManifest(BaseModel):
    """The declarative spec at `connectors/<id>/manifest.yaml`."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        description="Stable slug, e.g. 'gmail'. Tiles bind to this.",
        pattern=SLUG_PATTERN,
    )
    app: str = Field(description="Display name of the application, e.g. 'Gmail'.")
    kind: ConnectorKind = Field(description="mcp | mock | custom.")
    endpoint: str | None = Field(
        default=None,
        description="MCP server URL/ref. Required when kind=mcp.",
    )
    auth: AuthConfig = Field(default_factory=AuthConfig)
    tools: list[ToolSpec] = Field(
        default_factory=list,
        description="The app's tool surface — the superset tiles draw from.",
    )

    @model_validator(mode="after")
    def _check_kind_invariants(self) -> ConnectorManifest:
        if self.kind is ConnectorKind.MCP and not self.endpoint:
            raise ValueError("connector kind=mcp requires an 'endpoint'")

        names = [t.name for t in self.tools]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate tool names in connector '{self.id}': {sorted(dupes)}")
        return self

    def tool_names(self) -> set[str]:
        """Return the set of tool names this connector exposes."""
        return {t.name for t in self.tools}

    def get_tool(self, name: str) -> ToolSpec | None:
        """Return the named tool spec, or None if the connector lacks it."""
        return next((t for t in self.tools if t.name == name), None)
