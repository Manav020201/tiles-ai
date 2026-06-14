"""Cross-manifest validation + manifest loading.

Intra-manifest invariants live on the Pydantic models themselves (a tile can't
allow-list tools with no connector, a mcp connector needs an endpoint, etc.).
This module owns the checks that need *two* manifests together — does a tile's
bound connector exist, are its allow-listed tools real, does a read_only tile
secretly allow-list a side-effectful tool?

These are pure functions so the registry (phase 2) is a thin caller and the
tests (phase 1) can exercise the rules directly.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .connector_manifest import ConnectorManifest
from .permissions import PermissionTier
from .tile_manifest import TileManifest


class ContractError(Exception):
    """A manifest or cross-manifest rule was violated."""


# --- loading ---------------------------------------------------------------


def load_connector_manifest(path: str | Path) -> ConnectorManifest:
    """Parse and validate a connector manifest YAML file."""
    data = _read_yaml(path)
    return ConnectorManifest.model_validate(data)


def load_tile_manifest(path: str | Path) -> TileManifest:
    """Parse and validate a tile manifest YAML file."""
    data = _read_yaml(path)
    return TileManifest.model_validate(data)


def _read_yaml(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ContractError(f"manifest at {path} is not a mapping")
    return data


# --- cross-manifest checks -------------------------------------------------


def validate_tile_against_connector(
    tile: TileManifest, connector: ConnectorManifest | None
) -> list[str]:
    """Return a list of human-readable errors (empty == valid).

    Checks, in order:
      * a tile that binds a connector resolves to an existing one;
      * an instant tile (no connector) allow-lists nothing — already guaranteed
        by the tile model, re-asserted here for a single source of truth;
      * every allow-listed tool exists on the connector's surface;
      * a read_only tile does not allow-list a side-effectful tool.
    """
    errors: list[str] = []

    if tile.connector is None:
        # Instant tile: nothing to resolve. The tile model already forbids
        # allow-listing tools without a connector, but assert defensively.
        if tile.allowed_tools:
            errors.append(f"tile '{tile.id}' allow-lists tools but binds to no connector")
        return errors

    if connector is None:
        errors.append(
            f"tile '{tile.id}' binds to connector '{tile.connector}', which was "
            "not found in the registry"
        )
        return errors

    if connector.id != tile.connector:
        errors.append(
            f"tile '{tile.id}' bound connector '{tile.connector}' but was checked "
            f"against connector '{connector.id}'"
        )

    surface = connector.tool_names()
    for tool in tile.allowed_tools:
        if tool not in surface:
            errors.append(
                f"tile '{tile.id}' allow-lists tool '{tool}', which connector "
                f"'{connector.id}' does not expose. Available: {sorted(surface)}"
            )

    if tile.permission_tier is PermissionTier.READ_ONLY:
        for tool in tile.allowed_tools:
            spec = connector.get_tool(tool)
            if spec is not None and spec.side_effect:
                errors.append(
                    f"read_only tile '{tile.id}' allow-lists side-effectful tool "
                    f"'{tool}'. A read_only tile may not touch the outside world."
                )

    return errors


def assert_tile_valid(tile: TileManifest, connector: ConnectorManifest | None) -> None:
    """Raise ContractError if the tile/connector pairing is invalid."""
    errors = validate_tile_against_connector(tile, connector)
    if errors:
        raise ContractError("; ".join(errors))
