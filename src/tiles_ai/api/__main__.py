"""Run the Tiles AI API: `python -m tiles_ai.api`.

Discovers connectors/tiles from TILES_ROOT (default: cwd) and loads the brain
store from TILES_BRAIN (default: brain.local.yaml). The brain store is created
empty if the file is absent — the onboarding flow writes it.
"""

from __future__ import annotations

import os

import uvicorn

from ..contracts import HostedProvider
from ..model import BrainStore, ModelAdapter, echo_client_factory
from .app import create_app


def main() -> None:
    root = os.environ.get("TILES_ROOT", ".")

    if os.environ.get("TILES_ECHO"):
        # Zero-setup demo: an offline echo brain so the whole board works without
        # keys or a network. Great for a first look and for contributors.
        store = BrainStore()
        store.add_provider(
            HostedProvider(
                id="demo", provider="anthropic", api_key="demo", model="claude-opus-4-8"
            ),
            make_default=True,
        )
        adapter = ModelAdapter(store, client_factory=echo_client_factory)
        app = create_app(root=root, brain_store=store, model_adapter=adapter)
    else:
        brain_path = os.environ.get("TILES_BRAIN", "brain.local.yaml")
        store = BrainStore.load(brain_path)
        app = create_app(root=root, brain_store=store)

    uvicorn.run(
        app,
        host=os.environ.get("TILES_HOST", "127.0.0.1"),
        port=int(os.environ.get("TILES_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
