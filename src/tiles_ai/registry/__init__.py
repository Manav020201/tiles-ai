"""The registry layer — filesystem discovery + loading of connectors and tiles.

Promotes manifests on disk (`defined`) to loaded, validated, idle entries
(`available`). See `Registry.discover`.
"""

from __future__ import annotations

from .loader import (
    LoaderError,
    load_connector_adapter,
    load_interface_class,
    load_tile_handler,
)
from .registry import (
    LoadedConnector,
    LoadedTile,
    LoadError,
    Registry,
)

__all__ = [
    "Registry",
    "LoadedConnector",
    "LoadedTile",
    "LoadError",
    "LoaderError",
    "load_interface_class",
    "load_connector_adapter",
    "load_tile_handler",
]
