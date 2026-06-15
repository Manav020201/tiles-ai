#!/usr/bin/env python3
"""Assemble the starter board bundled into the wheel.

Copies the repo's board (connectors/, tiles/, examples/, sample_docs/) into
``src/tiles_ai/starter_board/`` so ``tiles init`` — and ``tiles up`` on an empty
directory — can seed it for users who installed from PyPI. Run this before
``python -m build`` (the release workflow does). The output dir is gitignored:
it is generated, never committed.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "src" / "tiles_ai" / "starter_board"
DIRS = ("connectors", "tiles", "examples", "sample_docs")
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.local.yaml", "*.local.json")


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    for name in DIRS:
        src = REPO / name
        if not src.is_dir():
            print(f"error: missing board dir {src}", file=sys.stderr)
            return 1
        shutil.copytree(src, DEST / name, ignore=_IGNORE)
    print(f"Bundled starter board -> {DEST.relative_to(REPO)} ({', '.join(DIRS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
