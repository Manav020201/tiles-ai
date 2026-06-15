"""Seed a working board into a directory.

A freshly ``pip install``-ed Tiles has no tiles or connectors in the user's
current directory, so ``tiles up`` would show an empty board. The package bundles
a starter board (the same one in this repo) under ``tiles_ai/starter_board/``;
``tiles init`` — and ``tiles up`` on an empty directory — copies it into place so
the user gets a real, editable board to learn from.

The bundle is generated at release-build time (see ``scripts/bundle_starter.py``)
and is absent in a source checkout, where the top-level ``tiles/`` and
``connectors/`` already exist. ``bundled_board()`` returns ``None`` in that case.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# The directories that make up a board. connectors/ + tiles/ are the board
# itself; examples/ + sample_docs/ back the bundled local-files connector
# (its endpoint launches examples/mcp_servers/files_server.py over sample_docs/).
BOARD_DIRS = ("connectors", "tiles", "examples", "sample_docs")

# Never copy build artifacts or local secrets into a freshly seeded board.
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.local.yaml", "*.local.json")


class BoardExistsError(Exception):
    """Raised when a board already exists at the destination."""


def bundled_board() -> Path | None:
    """Path to the starter board bundled in the package, or ``None`` in a source
    checkout (where the bundle is generated only at release-build time)."""
    path = Path(__file__).parent / "starter_board"
    return path if (path / "tiles").is_dir() else None


def has_board(dest: str | Path) -> bool:
    """True if ``dest`` already looks like a board (has tiles/ or connectors/)."""
    dest = Path(dest)
    return (dest / "tiles").is_dir() or (dest / "connectors").is_dir()


def init_board(
    dest: str | Path,
    source: str | Path | None = None,
    force: bool = False,
) -> list[str]:
    """Copy the starter board into ``dest``; return the directory names created.

    ``source`` defaults to the bundled board. Raises :class:`BoardExistsError`
    if ``dest`` already has a board and ``force`` is False, and
    :class:`FileNotFoundError` if no starter board is available.
    """
    dest = Path(dest)
    src = Path(source) if source is not None else bundled_board()
    if src is None:
        raise FileNotFoundError(
            "No bundled starter board found. Install tiles-ai from PyPI, or run "
            "from a repo checkout that already has tiles/ and connectors/."
        )
    if has_board(dest) and not force:
        raise BoardExistsError(f"{dest} already has a board (tiles/ or connectors/)")

    dest.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name in BOARD_DIRS:
        sub = src / name
        if not sub.is_dir():
            continue
        shutil.copytree(sub, dest / name, ignore=_IGNORE, dirs_exist_ok=force)
        created.append(name)
    return created
