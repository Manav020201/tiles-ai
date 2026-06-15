"""An import-string app factory for `uvicorn --reload`.

uvicorn's reloader re-imports the app in a worker process on file change, so it
needs a factory it can import by name rather than a pre-built app object. The
factory reads its config from the environment (set by `tiles up --reload`):

  TILES_ROOT   board root holding connectors/ and tiles/ (default: ".")
  TILES_BRAIN  brain store file (default: brain.local.yaml)
  TILES_ECHO   if set, use an offline demo brain (no keys)
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from .app import create_app


def make_app() -> FastAPI:
    root = os.environ.get("TILES_ROOT", ".")

    if os.environ.get("TILES_ECHO"):
        from ..contracts import HostedProvider
        from ..model import BrainStore, ModelAdapter, echo_client_factory

        store = BrainStore()
        store.add_provider(
            HostedProvider(
                id="demo", provider="anthropic", api_key="demo", model="claude-opus-4-8"
            ),
            make_default=True,
        )
        return create_app(
            root=root,
            brain_store=store,
            model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
        )

    from ..model import BrainStore

    brain = os.environ.get("TILES_BRAIN", "brain.local.yaml")
    return create_app(root=root, brain_store=BrainStore.load(brain))
