"""Scaffold a new tile folder (manifest + handler + README).

Shared by the `tiles new` CLI and the board's "create tile" endpoint, so both
produce identical, valid tiles. The manifest is built as a dict and validated
against `TileManifest` *before* anything is written — a scaffold either produces
a tile that loads, or it raises and writes nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .contracts import (
    ConnectorManifest,
    TileManifest,
    validate_tile_against_connector,
)
from .contracts.ids import SLUG_PATTERN


class ScaffoldError(Exception):
    """A tile could not be scaffolded (bad id, collision, invalid manifest)."""


def class_name(tile_id: str) -> str:
    """PascalCase class name from a tile id: 'my-tile' -> 'MyTile'."""
    return "".join(part.capitalize() for part in re.split(r"[-_]", tile_id) if part)


def slugify(text: str) -> str:
    """A tile-id slug from free text: 'My Cool Tile!' -> 'my-cool-tile'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "tile"


def build_manifest(
    *,
    id: str,
    name: str,
    description: str = "One line shown on the board.",
    icon: str = "🔲",
    instructions: str = "The system prompt / role for this tile's agent.",
    permission_tier: str = "read_only",
    connector: str | None = None,
    allowed_tools: list[str] | None = None,
    wants_input: bool = True,
    input_hint: str | None = None,
) -> dict:
    """Build a tile manifest dict and validate it. Raises ScaffoldError if invalid."""
    if not re.match(SLUG_PATTERN, id):
        raise ScaffoldError(f"'{id}' is not a valid id (lowercase letters/digits, - or _).")

    manifest: dict = {
        "id": id,
        "name": name,
        "description": description,
        "icon": icon,
        "permission_tier": permission_tier,
        "instructions": instructions,
    }
    if connector:
        manifest["connector"] = connector
        manifest["allowed_tools"] = list(allowed_tools or [])
    if wants_input:
        manifest["consumes"] = [{"name": "input", "description": input_hint or "Type here…"}]

    try:
        TileManifest.model_validate(manifest)
    except Exception as exc:  # surface pydantic's message cleanly
        raise ScaffoldError(f"invalid tile: {exc}") from exc
    return manifest


def _handler_source(manifest: dict) -> str:
    cls = class_name(manifest["id"])
    name = manifest["name"]
    if not manifest.get("connector"):
        return (
            f'"""{name} — an instant tile (input -> brain -> result)."""\n\n'
            "from tiles_ai.handlers import PromptTile\n\n\n"
            f"class {cls}(PromptTile):\n"
            '    """Behavior comes from manifest.yaml (instructions). Edit it there."""\n'
        )
    tools = manifest.get("allowed_tools") or []
    hint = (
        f'        # data = await context.tools.call("{tools[0]}", {{}})  # an allow-listed read\n'
        if tools
        else "        # read via context.tools.call(name, args)  # allow-listed only\n"
    )
    return (
        f'"""{name} handler. Edit `run` to do what you want."""\n\n'
        "from tiles_ai.contracts import ActionPlan, Tile\n\n\n"
        f"class {cls}(Tile):\n"
        "    async def run(self, input, context) -> ActionPlan:\n"
        f"{hint}"
        "        # propose side effects via ActionPlan(actions=[...]); don't run them inline\n"
        "        answer = await context.model.complete(\n"
        "            str(input), system=context.manifest.instructions\n"
        "        )\n"
        "        return ActionPlan(result=answer)\n"
    )


def update_tile(
    root: str | Path,
    tile_id: str,
    changes: dict,
    connector_manifest: ConnectorManifest | None = None,
) -> Path:
    """Update a tile's manifest fields in place, keeping its handler.py.

    Only the declarative fields are editable from the board (name, icon,
    description, instructions, permission_tier, wants_input/input_hint) — the
    handler's logic stays in code. Validates schema + (if bound) the connector
    before writing; raises ScaffoldError otherwise.
    """
    folder = Path(root) / "tiles" / tile_id
    mpath = folder / "manifest.yaml"
    if not mpath.exists():
        raise ScaffoldError(f"no tile '{tile_id}'.")

    data = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}
    for key in ("name", "icon", "description", "instructions", "permission_tier"):
        if changes.get(key) is not None:
            data[key] = changes[key]
    if changes.get("wants_input") is not None:
        if changes["wants_input"]:
            existing = (data.get("consumes") or [{}])[0].get("description")
            data["consumes"] = [
                {
                    "name": "input",
                    "description": changes.get("input_hint") or existing or "Type here…",
                }
            ]
        else:
            data.pop("consumes", None)

    try:
        manifest = TileManifest.model_validate(data)
    except Exception as exc:
        raise ScaffoldError(f"invalid tile: {exc}") from exc
    if connector_manifest is not None:
        errors = validate_tile_against_connector(manifest, connector_manifest)
        if errors:
            raise ScaffoldError("; ".join(errors))

    mpath.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return folder


def scaffold_connector(
    root: str | Path,
    *,
    id: str,
    app: str,
    kind: str = "mcp",
    endpoint: str | None = None,
    env: list[str] | None = None,
    tools: list[dict] | None = None,
) -> Path:
    """Validate + write a new connector folder under `<root>/connectors/<id>/`.

    `kind="mcp"` scaffolds an `MCPConnector` subclass pointed at `endpoint`;
    `kind="mock"` scaffolds a `MockConnector`. The tool surface (with side_effect
    flags) is the authority the gate trusts. Raises ScaffoldError on a bad id,
    collision, or invalid manifest (nothing is written then).
    """
    if not re.match(SLUG_PATTERN, id):
        raise ScaffoldError(f"'{id}' is not a valid id (lowercase letters/digits, - or _).")

    manifest: dict = {"id": id, "app": app, "kind": kind}
    if kind == "mcp":
        if not endpoint:
            raise ScaffoldError("an MCP connector needs an endpoint command.")
        manifest["endpoint"] = endpoint
    if env:
        manifest["auth"] = {"scheme": "api_key", "env": list(env)}
    manifest["tools"] = [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "side_effect": bool(t.get("side_effect")),
        }
        for t in (tools or [])
    ]

    try:
        ConnectorManifest.model_validate(manifest)
    except Exception as exc:
        raise ScaffoldError(f"invalid connector: {exc}") from exc

    folder = Path(root) / "connectors" / id
    if folder.exists():
        raise ScaffoldError(f"a connector named '{id}' already exists.")

    base = "MCPConnector" if kind == "mcp" else "MockConnector"
    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (folder / "adapter.py").write_text(
        f'"""{app} connector. Generated; the logic lives in {base}."""\n\n'
        f"from tiles_ai.connectors import {base}\n\n\n"
        f"class {class_name(id)}({base}):\n"
        f'    """Edit manifest.yaml to change the tool surface or endpoint."""\n',
        encoding="utf-8",
    )
    (folder / "README.md").write_text(
        f"# {app} connector\n\nGenerated from Tiles AI. See docs/AUTHORING.md.\n",
        encoding="utf-8",
    )
    return folder


def scaffold_tile(root: str | Path, **fields) -> Path:
    """Validate + write a new tile folder under `<root>/tiles/<id>/`.

    Returns the created folder. Raises ScaffoldError on a bad id, a name
    collision, or an invalid manifest (nothing is written in that case).
    """
    manifest = build_manifest(**fields)
    folder = Path(root) / "tiles" / manifest["id"]
    if folder.exists():
        raise ScaffoldError(f"a tile named '{manifest['id']}' already exists.")

    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (folder / "handler.py").write_text(_handler_source(manifest), encoding="utf-8")
    (folder / "README.md").write_text(
        f"# {manifest['name']}\n\n{manifest['description']}\n\n"
        "Created from Tiles AI. Edit `manifest.yaml` and `handler.py`; see "
        "docs/AUTHORING.md.\n",
        encoding="utf-8",
    )
    return folder
