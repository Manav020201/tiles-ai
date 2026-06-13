"""The model adapter — resolve a tile's brain, then run a completion through it.

This is the runtime's single entry point to "the brain". It owns:
  * the brain store (provider config + default),
  * brain resolution (tile pin -> global default), delegated to the contract,
  * dispatch to the right `ModelClient` for a resolved brain,
  * the per-provider Test action (a trivial completion -> ok/error).

The client factory is injectable so the runtime and tests can run fully offline
(echo) while production wires the real hosted/local clients. The default factory
picks a real client by provider kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..contracts import (
    BrainConfig,
    BrainResolutionError,
    HostedProvider,
    LocalProvider,
    ModelRef,
    ResolvedBrain,
    resolve_brain,
)
from .clients import (
    AnthropicClient,
    EchoModelClient,
    ModelClient,
    ModelClientError,
    OllamaClient,
    OpenAIClient,
)
from .store import BrainStore

# Given a resolved brain + the full config (for credentials), build a client.
ClientFactory = Callable[[ResolvedBrain, BrainConfig], ModelClient]


def default_client_factory(resolved: ResolvedBrain, config: BrainConfig) -> ModelClient:
    """Build a real client for a resolved brain, using stored credentials.

    Matches the resolved brain back to its configured provider to pull the
    api_key / endpoint, then dispatches by provider kind. Raises if the brain
    cannot be backed by a configured provider (e.g. a pin with no matching key).
    """
    provider = config.get(resolved.provider_id) if resolved.provider_id else None
    if provider is None:
        raise ModelClientError(
            f"resolved brain ({resolved.badge_label}) has no configured provider "
            "to supply credentials. Configure it in the brain store first."
        )
    if isinstance(provider, LocalProvider):
        return OllamaClient(endpoint=provider.endpoint, model=provider.model)
    if isinstance(provider, HostedProvider):
        builder = _HOSTED_CLIENTS.get(provider.provider)
        if builder is None:
            raise ModelClientError(
                f"hosted provider '{provider.provider}' has no v0 client. "
                f"Wired: {sorted(_HOSTED_CLIENTS)}. Register one via register_hosted_client."
            )
        return builder(provider.api_key, provider.model)
    raise ModelClientError(f"unknown provider kind for '{resolved.provider_id}'")


# Hosted-provider client builders, keyed by provider family. The mapping is the
# single extension point: add a provider by registering a builder, no edits to
# the dispatch logic above.
_HOSTED_CLIENTS: dict[str, Callable[[str, str], ModelClient]] = {
    "anthropic": lambda key, model: AnthropicClient(api_key=key, model=model),
    "openai": lambda key, model: OpenAIClient(api_key=key, model=model),
}


def register_hosted_client(
    provider: str, builder: Callable[[str, str], ModelClient]
) -> None:
    """Register a client builder for a hosted provider family (api_key, model)."""
    _HOSTED_CLIENTS[provider] = builder


def echo_client_factory(resolved: ResolvedBrain, config: BrainConfig) -> ModelClient:
    """A factory that always returns an offline echo client. For tests/demos."""
    return EchoModelClient(model=resolved.model)


@dataclass
class TestResult:
    """Outcome of a provider Test action."""

    ok: bool
    detail: str = ""


class ModelAdapter:
    """Resolve brains and run completions; the runtime's handle on the model."""

    def __init__(
        self,
        store: BrainStore,
        *,
        client_factory: ClientFactory = default_client_factory,
    ) -> None:
        self.store = store
        self._client_factory = client_factory

    @property
    def config(self) -> BrainConfig:
        return self.store.config

    def resolve(self, tile_model: ModelRef | None) -> ResolvedBrain:
        """Resolve which brain a tile runs on (pin -> default). May raise."""
        return resolve_brain(tile_model, self.store.config)

    def client_for(self, resolved: ResolvedBrain) -> ModelClient:
        return self._client_factory(resolved, self.store.config)

    async def complete(
        self, resolved: ResolvedBrain, prompt: str, *, system: str | None = None
    ) -> str:
        """Run one completion through the brain a tile resolved to."""
        client = self.client_for(resolved)
        return await client.complete(prompt, system=system)

    async def test(self, provider_id: str) -> TestResult:
        """Run a trivial completion against a provider; report ok/error.

        This is what gives the user a green check before relying on a brain.
        """
        provider = self.store.config.get(provider_id)
        if provider is None:
            return TestResult(ok=False, detail=f"no provider '{provider_id}'")
        resolved = ResolvedBrain(
            source="default",
            provider=provider.provider_family(),
            model=provider.model,
            endpoint=getattr(provider, "endpoint", None),
            provider_id=provider.id,
        )
        try:
            text = await self.complete(resolved, "Reply with 'ok'.")
            return TestResult(ok=True, detail=text[:120])
        except (ModelClientError, BrainResolutionError) as exc:
            return TestResult(ok=False, detail=str(exc))
