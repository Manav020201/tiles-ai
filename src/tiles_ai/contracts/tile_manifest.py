"""Tile manifest schema.

A *tile* is the agent on top of a connector: a model + instructions +
permission tier, bound to (at most) one connector and allow-listed to a subset
of that connector's tools. It is the unit the board paints and the user taps.

Two deliberate shapes:

  * `connector` is OPTIONAL. "Instant" tiles (Ask, Summarize) need no app at
    all — they prove the brain works in ~10 seconds with zero setup. A tile
    with no connector may not allow-list any tools.

  * `model` (a `ModelRef`) is OPTIONAL and SECRET-FREE. A tile with no model
    uses the user's global default brain — this is what lets a beginner connect
    once and never configure a model per tile. A `ModelRef` declares *which*
    model, never an API key; secrets live only in the local brain store.

This module defines the on-disk shape of `tiles/<id>/manifest.yaml`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ids import SLUG_PATTERN
from .permissions import PermissionTier


class ModelRef(BaseModel):
    """A pinned model declaration — *what* model, never a secret.

    Carrying no `api_key` is intentional: manifests are checked into repos.
    Credentials are resolved at run time from the local brain store by matching
    this reference against a configured provider. See
    `provider_config.resolve_brain`.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        description="Provider family, e.g. 'anthropic', 'openai', 'ollama'."
    )
    model: str = Field(description="Model name, e.g. 'claude-opus-4-8', 'llama3'.")
    endpoint: str | None = Field(
        default=None,
        description="Endpoint for local/self-hosted models, e.g. http://localhost:11434.",
    )


class Capability(BaseModel):
    """A named input or output a tile advertises — the composition seam.

    `provides`/`consumes` are how a tile declares what it exposes to, or expects
    from, the rest of the system. v0 does not wire tile-to-tile composition, but
    the contract must carry these so multi-tile collaboration plugs in later
    without a schema change.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Capability slug, e.g. 'email.summary'.")
    description: str = Field(default="", description="One line: what it is.")
    schema_ref: dict | None = Field(
        default=None,
        description="Optional JSON Schema describing the payload shape.",
    )


class TileManifest(BaseModel):
    """The declarative spec at `tiles/<id>/manifest.yaml`."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable unique slug, e.g. 'gmail-draft'.", pattern=SLUG_PATTERN)
    name: str = Field(description="Display name.")
    description: str = Field(description="One line, shown on the board.")
    icon: str = Field(default="🔲", description="Emoji or asset ref for board display.")

    connector: str | None = Field(
        default=None,
        description="Connector id this tile binds to. Omit for instant tiles.",
    )
    model: ModelRef | None = Field(
        default=None,
        description="Pinned model. Omit to use the global default brain.",
    )
    instructions: str = Field(description="System prompt / role for the agent.")
    allowed_tools: list[str] = Field(
        default_factory=list,
        description=(
            "Allow-list: subset of the connector's tools this tile may call. "
            "A tile sees only what it is granted, not the whole app surface."
        ),
    )
    permission_tier: PermissionTier = Field(
        description="read_only | draft | autonomous."
    )

    # Composition seams (reserved; declared so future work plugs in cleanly).
    provides: list[Capability] = Field(default_factory=list)
    consumes: list[Capability] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_invariants(self) -> "TileManifest":
        if self.allowed_tools and not self.connector:
            raise ValueError(
                f"tile '{self.id}' allow-lists tools {self.allowed_tools} but binds "
                "to no connector. Set 'connector', or remove 'allowed_tools'."
            )

        dupes = {t for t in self.allowed_tools if self.allowed_tools.count(t) > 1}
        if dupes:
            raise ValueError(
                f"tile '{self.id}' has duplicate allowed_tools: {sorted(dupes)}"
            )

        # read_only tiles must not allow-list a side-effectful tool. We can only
        # *fully* enforce this against a connector (see
        # validation.validate_tile_against_connector); here we just guard the
        # intra-manifest invariants. Cross-manifest checks live in `validation`.
        return self

    def uses_default_brain(self) -> bool:
        """True if this tile relies on the global default brain (no pin)."""
        return self.model is None
