"""The "brain" layer — global model-provider config and resolution.

This is the layer that makes onboarding zero-friction. Tiles do not each carry
a full model setup. The user configures one or more providers once, picks a
`default_provider`, and every tile uses that brain unless it pins its own.

Two kinds of provider:
  * hosted — a cloud API (anthropic | openai | ...) with an `api_key`.
  * local  — a local server (Ollama, etc.) reachable at an `endpoint`.

Keys are stored locally only: the app runs on the user's machine, keys never
leave it and are never sent to any project-owned server. This config is the
secret-holding store; tile manifests (`ModelRef`) are deliberately secret-free.

Resolution order at run time: a tile's pinned `model` -> else `default_provider`.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ids import SLUG_PATTERN
from .tile_manifest import ModelRef


class ProviderKind(str, Enum):
    HOSTED = "hosted"
    LOCAL = "local"


class HostedProvider(BaseModel):
    """A cloud LLM provider configured with an API key (stored locally)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable slug for this provider config.", pattern=SLUG_PATTERN)
    kind: Literal[ProviderKind.HOSTED] = ProviderKind.HOSTED
    provider: str = Field(description="anthropic | openai | ...")
    api_key: str = Field(description="Secret. Stored locally only; never transmitted to us.")
    model: str = Field(description="Default model for this provider, e.g. 'claude-opus-4-8'.")

    def provider_family(self) -> str:
        """The provider family a ModelRef matches against (the cloud vendor)."""
        return self.provider

    def matches(self, ref: "ModelRef") -> bool:
        """True if a tile's pinned ModelRef resolves to this provider."""
        return ref.provider == self.provider and ref.model == self.model


class LocalProvider(BaseModel):
    """A local/self-hosted LLM endpoint (Ollama or any OpenAI-compatible server)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable slug for this provider config.", pattern=SLUG_PATTERN)
    kind: Literal[ProviderKind.LOCAL] = ProviderKind.LOCAL
    endpoint: str = Field(description="e.g. http://localhost:11434")
    model: str = Field(description="A downloaded model, e.g. 'llama3'.")

    def provider_family(self) -> str:
        """Local providers report a 'local' family for badge display."""
        return "local"

    def matches(self, ref: "ModelRef") -> bool:
        """True if a tile's pinned ModelRef resolves to this local provider.

        Matched on endpoint + model, since a local 'provider' name is arbitrary.
        """
        return ref.endpoint == self.endpoint and ref.model == self.model


# Discriminated union on `kind` — Pydantic picks the right class automatically
# and gives clean errors when neither shape matches.
Provider = Annotated[Union[HostedProvider, LocalProvider], Field(discriminator="kind")]


class BrainConfig(BaseModel):
    """The user's global provider config + chosen default brain.

    This is the local, secret-holding store the onboarding flow writes. It is
    NOT checked into a repo (see .gitignore) — it is per-machine user state.
    """

    model_config = ConfigDict(extra="forbid")

    providers: list[Provider] = Field(default_factory=list)
    default_provider: str | None = Field(
        default=None,
        description="Id of the global default brain. Tiles with no model use it.",
    )

    @model_validator(mode="after")
    def _check(self) -> "BrainConfig":
        ids = [p.id for p in self.providers]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate provider ids: {sorted(dupes)}")
        if self.default_provider and self.default_provider not in ids:
            raise ValueError(
                f"default_provider '{self.default_provider}' is not a configured "
                f"provider. Configured: {sorted(ids)}."
            )
        return self

    def get(self, provider_id: str) -> Provider | None:
        return next((p for p in self.providers if p.id == provider_id), None)


class ResolvedBrain(BaseModel):
    """The outcome of resolving which brain a tile runs on.

    `source` is what the board's brain badge shows: "default" (the global
    brain) or "pinned" (the tile pinned its own model). `provider_id` is the
    configured provider whose credentials/endpoint back this run, when one was
    found; for a pin with no matching configured provider it may be None (the
    model_adapter in phase 3 decides whether that is runnable).
    """

    model_config = ConfigDict(extra="forbid")

    source: Literal["default", "pinned"]
    provider: str
    model: str
    endpoint: str | None = None
    provider_id: str | None = None

    @property
    def badge_label(self) -> str:
        """Short label for the board's resolved-brain badge."""
        return "default" if self.source == "default" else f"pinned:{self.provider}/{self.model}"


class BrainResolutionError(Exception):
    """Raised when a tile's brain cannot be resolved (no pin, no default)."""


def resolve_brain(tile_model: ModelRef | None, config: BrainConfig) -> ResolvedBrain:
    """Resolve which brain a tile runs on.

    Resolution order:
        1. The tile's pinned `model` (a `ModelRef`), if present. We try to match
           it to a configured provider (by provider family + model) to attach
           credentials/endpoint; if none matches we still return the pinned spec
           so the badge is honest and the adapter can decide runnability.
        2. Otherwise the global `default_provider`.

    Raises:
        BrainResolutionError: the tile has no pin and no default is configured.
            This is the case onboarding exists to prevent.
    """
    if tile_model is not None:
        match = next((p for p in config.providers if p.matches(tile_model)), None)
        return ResolvedBrain(
            source="pinned",
            provider=tile_model.provider,
            model=tile_model.model,
            endpoint=tile_model.endpoint
            or (getattr(match, "endpoint", None) if match else None),
            provider_id=match.id if match else None,
        )

    if not config.default_provider:
        raise BrainResolutionError(
            "Tile uses the default brain but no default_provider is configured. "
            "Complete the 'Connect a brain' onboarding first."
        )

    default = config.get(config.default_provider)
    assert default is not None  # guaranteed by BrainConfig validation
    return ResolvedBrain(
        source="default",
        provider=default.provider_family(),
        model=default.model,
        endpoint=getattr(default, "endpoint", None),
        provider_id=default.id,
    )
