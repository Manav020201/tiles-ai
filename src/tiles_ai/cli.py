"""The `tiles` command-line interface.

    tiles up                 run the API + board (http://127.0.0.1:8000)
    tiles up --echo          run with an offline demo brain (no keys)
    tiles list               show discovered connectors and tiles
    tiles new <id>           scaffold a new tile folder

Thin by design: every subcommand is a few lines over the library. See
`tiles_ai.api`, `tiles_ai.registry`, and `docs/AUTHORING.md`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .contracts.ids import SLUG_PATTERN


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tiles", description="Tiles AI — a control plane for your AI agents."
    )
    parser.add_argument("--version", action="version", version=f"tiles-ai {__version__}")
    sub = parser.add_subparsers(dest="command")

    up = sub.add_parser("up", help="Run the API and board.")
    up.add_argument("--root", default=".", help="Board root holding connectors/ and tiles/.")
    up.add_argument("--host", default="127.0.0.1")
    up.add_argument("--port", type=int, default=8000)
    up.add_argument("--brain", default="brain.local.yaml", help="Brain store file.")
    up.add_argument("--echo", action="store_true", help="Use an offline demo brain (no keys).")
    up.set_defaults(func=_up)

    ls = sub.add_parser("list", help="List discovered connectors and tiles.")
    ls.add_argument("--root", default=".")
    ls.set_defaults(func=_list)

    new = sub.add_parser("new", help="Scaffold a new tile.")
    new.add_argument("id", help="Tile id / folder name (slug).")
    new.add_argument("--root", default=".")
    new.add_argument(
        "--connector", default=None, help="Bind to a connector (omit for an instant tile)."
    )
    new.add_argument("--tier", default="read_only", choices=["read_only", "draft", "autonomous"])
    new.set_defaults(func=_new)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args) or 0


def _up(args) -> int:
    import uvicorn

    from .api import create_app
    from .model import BrainStore

    if args.echo:
        from .contracts import HostedProvider
        from .model import ModelAdapter, echo_client_factory

        store = BrainStore()
        store.add_provider(
            HostedProvider(
                id="demo", provider="anthropic", api_key="demo", model="claude-opus-4-8"
            ),
            make_default=True,
        )
        app = create_app(
            root=args.root,
            brain_store=store,
            model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
        )
        print("Running with an offline demo brain (echo). No keys, no network.")
    else:
        app = create_app(root=args.root, brain_store=BrainStore.load(args.brain))

    print(f"Tiles AI on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _list(args) -> int:
    from .registry import Registry

    reg = Registry.discover(args.root)
    print(f"{len(reg.connectors)} connector(s):")
    for cid in sorted(reg.connectors):
        kind = reg.connectors[cid].manifest.kind.value
        print(f"  - {cid}  ({kind})")
    print(f"{len(reg.tiles)} tile(s):")
    for tid in sorted(reg.tiles):
        m = reg.tiles[tid].manifest
        bind = f" -> {m.connector}" if m.connector else " (instant)"
        print(f"  - {tid}  [{m.permission_tier.value}]{bind}")
    if reg.errors:
        print(f"\n{len(reg.errors)} error(s):", file=sys.stderr)
        for err in reg.errors:
            print(f"  ! {err}", file=sys.stderr)
        return 1
    return 0


def _new(args) -> int:
    import re

    if not re.match(SLUG_PATTERN, args.id):
        print(f"error: '{args.id}' is not a valid slug (lowercase, - or _).", file=sys.stderr)
        return 1

    folder = Path(args.root) / "tiles" / args.id
    if folder.exists():
        print(f"error: {folder} already exists.", file=sys.stderr)
        return 1
    folder.mkdir(parents=True)

    title = args.id.replace("-", " ").replace("_", " ").title()
    instant = args.connector is None

    (folder / "manifest.yaml").write_text(
        _manifest_template(args, title, instant), encoding="utf-8"
    )
    (folder / "handler.py").write_text(_handler_template(args, title, instant), encoding="utf-8")
    (folder / "README.md").write_text(
        f"# {title}\n\nA Tiles AI tile. Edit `manifest.yaml` and implement `run` in "
        f"`handler.py`. See docs/AUTHORING.md.\n",
        encoding="utf-8",
    )
    print(f"Created tiles/{args.id}/ — edit manifest.yaml and handler.py, then `tiles list`.")
    return 0


def _manifest_template(args, title: str, instant: bool) -> str:
    lines = [
        f"id: {args.id}",
        f"name: {title}",
        "description: One line shown on the board.",
        'icon: "🔲"',
        f"permission_tier: {args.tier}",
    ]
    if not instant:
        lines += [
            f"connector: {args.connector}",
            "allowed_tools: []  # subset of the connector's tools",
        ]
    lines += [
        "instructions: >",
        "  The system prompt / role for this tile's agent.",
        "consumes:",
        "  - name: input",
        "    description: What to type…",
    ]
    return "\n".join(lines) + "\n"


def _handler_template(args, title: str, instant: bool) -> str:
    cls = title.replace(" ", "")
    if instant:
        return (
            f'"""{title} — an instant tile (input -> brain -> result)."""\n\n'
            "from tiles_ai.handlers import PromptTile\n\n\n"
            f"class {cls}(PromptTile):\n"
            f'    """Behavior comes from manifest.yaml (instructions)."""\n'
        )
    return (
        f'"""{title} handler."""\n\n'
        "from tiles_ai.contracts import ActionPlan, Tile\n\n\n"
        f"class {cls}(Tile):\n"
        "    async def run(self, input, context) -> ActionPlan:\n"
        "        # read via ctx.tools (allow-listed); propose side effects via ActionPlan\n"
        "        answer = await context.model.complete(str(input), system=context.manifest.instructions)\n"
        "        return ActionPlan(result=answer)\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
