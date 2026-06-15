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

from .contracts import TileManifest
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
