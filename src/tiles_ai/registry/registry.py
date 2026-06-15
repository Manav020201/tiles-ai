"""The registry — discover, validate, and load connectors and tiles.

The registry is the component that promotes a tile from `defined` (a manifest on
disk) to `available` (validated, dependencies satisfied, code loaded, idle). It
is intentionally thin: the hard rules live in `contracts` (intra-manifest
invariants) and `contracts.validation` (cross-manifest checks). The registry
orchestrates them over the filesystem and collects failures per item, so one
broken folder does not sink the whole board.

Discovery order matters: connectors load first (tiles bind to them), then tiles
are validated against the loaded connector set. A tile that binds to a missing
connector or a tool the connector does not expose is rejected — it never reaches
`available`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import (
    ConnectorManifest,
    TileManifest,
    TileState,
    load_connector_manifest,
    load_tile_manifest,
    validate_tile_against_connector,
)
from .loader import LoaderError, load_connector_adapter, load_tile_handler

CONNECTORS_DIRNAME = "connectors"
TILES_DIRNAME = "tiles"


@dataclass
class LoadedConnector:
    """A connector whose manifest validated and whose adapter class loaded."""

    manifest: ConnectorManifest
    adapter_cls: type
    path: Path

    @property
    def id(self) -> str:
        return self.manifest.id


@dataclass
class LoadedTile:
    """A tile that reached `available`: manifest valid, handler loaded, binding ok."""

    manifest: TileManifest
    handler_cls: type
    path: Path
    state: TileState = TileState.AVAILABLE

    @property
    def id(self) -> str:
        return self.manifest.id


@dataclass
class LoadError:
    """A connector or tile that failed to load, with human-readable reasons."""

    kind: str  # "connector" | "tile"
    source: str  # folder name or manifest id, whichever is known
    errors: list[str]

    def __str__(self) -> str:
        return f"[{self.kind}] {self.source}: " + "; ".join(self.errors)


@dataclass
class Registry:
    """Loaded connectors + tiles, plus the errors encountered building them."""

    connectors: dict[str, LoadedConnector] = field(default_factory=dict)
    tiles: dict[str, LoadedTile] = field(default_factory=dict)
    errors: list[LoadError] = field(default_factory=list)

    # --- queries -----------------------------------------------------------

    @property
    def ok(self) -> bool:
        """True if every discovered folder loaded without error."""
        return not self.errors

    def get_connector(self, connector_id: str) -> LoadedConnector | None:
        return self.connectors.get(connector_id)

    def get_tile(self, tile_id: str) -> LoadedTile | None:
        return self.tiles.get(tile_id)

    def tiles_for_connector(self, connector_id: str) -> list[LoadedTile]:
        """Every loaded tile bound to a given connector (the many-to-one fan-out)."""
        return [t for t in self.tiles.values() if t.manifest.connector == connector_id]

    def report(self) -> str:
        """A short human summary, handy for a CLI or startup log."""
        lines = [f"{len(self.connectors)} connector(s), {len(self.tiles)} tile(s) loaded."]
        if self.errors:
            lines.append(f"{len(self.errors)} error(s):")
            lines.extend(f"  - {e}" for e in self.errors)
        return "\n".join(lines)

    # --- discovery ---------------------------------------------------------

    @classmethod
    def discover(cls, root: str | Path) -> Registry:
        """Build a registry from `<root>/connectors` and `<root>/tiles`."""
        root = Path(root)
        registry = cls()
        registry._load_connectors(root / CONNECTORS_DIRNAME)
        registry._load_tiles(root / TILES_DIRNAME)
        return registry

    def rescan(self, root: str | Path) -> Registry:
        """Re-discover from disk in place, so existing references see new tiles.

        The same Registry object is mutated (not replaced), so closures and the
        runtime that captured it pick up newly added/edited tiles without rewiring.
        Active tiles keep running — the runtime tracks those separately.
        """
        fresh = Registry.discover(root)
        self.connectors = fresh.connectors
        self.tiles = fresh.tiles
        self.errors = fresh.errors
        return self

    def _load_connectors(self, connectors_dir: Path) -> None:
        for folder in _manifest_folders(connectors_dir):
            name = folder.name
            try:
                manifest = load_connector_manifest(folder / "manifest.yaml")
            except Exception as exc:  # noqa: BLE001 - report, don't crash the load
                self.errors.append(LoadError("connector", name, [str(exc)]))
                continue

            if manifest.id != name:
                self.errors.append(
                    LoadError(
                        "connector",
                        name,
                        [f"folder name '{name}' != manifest id '{manifest.id}'"],
                    )
                )
                continue

            if manifest.id in self.connectors:
                self.errors.append(
                    LoadError("connector", name, [f"duplicate connector id '{manifest.id}'"])
                )
                continue

            try:
                adapter_cls = load_connector_adapter(folder, manifest.id)
            except LoaderError as exc:
                self.errors.append(LoadError("connector", manifest.id, [str(exc)]))
                continue

            self.connectors[manifest.id] = LoadedConnector(manifest, adapter_cls, folder)

    def _load_tiles(self, tiles_dir: Path) -> None:
        for folder in _manifest_folders(tiles_dir):
            name = folder.name
            try:
                manifest = load_tile_manifest(folder / "manifest.yaml")
            except Exception as exc:  # noqa: BLE001 - report, don't crash the load
                self.errors.append(LoadError("tile", name, [str(exc)]))
                continue

            if manifest.id != name:
                self.errors.append(
                    LoadError(
                        "tile",
                        name,
                        [f"folder name '{name}' != manifest id '{manifest.id}'"],
                    )
                )
                continue

            if manifest.id in self.tiles:
                self.errors.append(LoadError("tile", name, [f"duplicate tile id '{manifest.id}'"]))
                continue

            # Cross-manifest: does the bound connector (and each allow-listed
            # tool) actually resolve? This is the dangling-binding rejection.
            bound = self.connectors.get(manifest.connector) if manifest.connector else None
            binding_errors = validate_tile_against_connector(
                manifest, bound.manifest if bound else None
            )
            if binding_errors:
                self.errors.append(LoadError("tile", manifest.id, binding_errors))
                continue

            try:
                handler_cls = load_tile_handler(folder, manifest.id)
            except LoaderError as exc:
                self.errors.append(LoadError("tile", manifest.id, [str(exc)]))
                continue

            self.tiles[manifest.id] = LoadedTile(manifest, handler_cls, folder)


def _manifest_folders(parent: Path) -> list[Path]:
    """Subdirectories of `parent` that contain a manifest.yaml, sorted by name.

    A missing parent dir yields nothing (a board may have no connectors yet).
    Folders without a manifest.yaml (e.g. a stray README dir) are skipped
    silently — only real manifest folders are candidates.
    """
    if not parent.is_dir():
        return []
    return sorted(
        (p for p in parent.iterdir() if p.is_dir() and (p / "manifest.yaml").is_file()),
        key=lambda p: p.name,
    )
