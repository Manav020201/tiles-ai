"""The brain store — where the global provider config lives on the machine.

This is the secret-holding store the onboarding flow writes (phase 5). It wraps
a `BrainConfig` with add/remove/set-default mutations and optional YAML
persistence. Keys never leave the machine; this file is gitignored
(`*.local.yaml`, `brain.local.*`).

Kept deliberately small: validation lives on `BrainConfig`, persistence is a
thin YAML round-trip, and the runtime reads `store.config` to resolve brains.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..contracts import BrainConfig, Provider


class BrainStore:
    """In-memory `BrainConfig` with optional file persistence."""

    def __init__(self, config: BrainConfig | None = None, *, path: str | Path | None = None):
        self._config = config or BrainConfig()
        self._path = Path(path) if path else None

    @classmethod
    def load(cls, path: str | Path) -> "BrainStore":
        """Load a brain store from a YAML file (or start empty if absent)."""
        p = Path(path)
        if not p.exists():
            return cls(BrainConfig(), path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls(BrainConfig.model_validate(data), path=p)

    @property
    def config(self) -> BrainConfig:
        return self._config

    def add_provider(self, provider: Provider, *, make_default: bool = False) -> None:
        """Add (or replace) a provider. Re-validates the whole config.

        If this is the first provider, it becomes the default automatically —
        the zero-friction case where a beginner configures exactly one brain.
        """
        providers = [p for p in self._config.providers if p.id != provider.id]
        providers.append(provider)
        default = self._config.default_provider
        if make_default or default is None:
            default = provider.id
        self._config = BrainConfig(providers=providers, default_provider=default)

    def remove_provider(self, provider_id: str) -> None:
        providers = [p for p in self._config.providers if p.id != provider_id]
        default = self._config.default_provider
        if default == provider_id:
            default = providers[0].id if providers else None
        self._config = BrainConfig(providers=providers, default_provider=default)

    def set_default(self, provider_id: str) -> None:
        self._config = BrainConfig(
            providers=self._config.providers, default_provider=provider_id
        )

    def save(self, path: str | Path | None = None) -> Path:
        """Persist to YAML. Uses the load path if none is given."""
        target = Path(path) if path else self._path
        if target is None:
            raise ValueError("no path to save the brain store to")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(self._config.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        self._path = target
        return target
