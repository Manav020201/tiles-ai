"""Dynamic loading of `adapter.py` / `handler.py` into their interface classes.

A connector folder ships an `adapter.py` that defines exactly one concrete
`Connector` subclass; a tile folder ships a `handler.py` that defines exactly
one concrete `Tile` subclass. There is no registration boilerplate — "copy a
folder, implement one interface" means the loader finds the class by structure,
not by a decorator the author has to remember.

The loader is deliberately strict: zero or many candidate classes is an error,
because either is ambiguous to the registry and confusing to a tile author.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path


class LoaderError(Exception):
    """Raised when a module can't be imported or its interface class can't be found."""


def _module_name(prefix: str, slug: str) -> str:
    """A unique, import-safe synthetic module name for a loaded file."""
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", slug)
    return f"tiles_ai._loaded.{prefix}.{safe}"


def load_interface_class(path: Path, base: type, *, module_name: str) -> type:
    """Import `path` and return the single concrete subclass of `base` it defines.

    Args:
        path: the .py file (adapter.py or handler.py).
        base: the interface base class (Connector or Tile).
        module_name: synthetic name to register the module under.

    Only classes *defined in this module* count — a re-exported or imported
    subclass (e.g. `from tiles_ai.contracts import Connector`) is ignored, so the
    base class itself and shared helpers never get mistaken for the impl.

    Raises:
        LoaderError: the file is missing, fails to import, or defines zero / more
            than one concrete subclass of `base`.
    """
    if not path.exists():
        raise LoaderError(f"expected {path.name} at {path}, but it does not exist")

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise LoaderError(f"could not create import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any author error verbatim
        sys.modules.pop(module_name, None)
        raise LoaderError(f"error importing {path}: {exc}") from exc

    candidates = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type)
        and issubclass(obj, base)
        and obj is not base
        and obj.__module__ == module.__name__
        and not inspect.isabstract(obj)
    ]

    if not candidates:
        raise LoaderError(
            f"{path.name} defines no concrete {base.__name__} subclass. "
            f"Define one class that subclasses {base.__name__}."
        )
    if len(candidates) > 1:
        names = ", ".join(sorted(c.__name__ for c in candidates))
        raise LoaderError(
            f"{path.name} defines multiple {base.__name__} subclasses ({names}). "
            "Exactly one is required so the registry knows which to load."
        )
    return candidates[0]


def load_connector_adapter(folder: Path, connector_id: str) -> type:
    from ..contracts import Connector

    return load_interface_class(
        folder / "adapter.py",
        Connector,
        module_name=_module_name("connectors", connector_id),
    )


def load_tile_handler(folder: Path, tile_id: str) -> type:
    from ..contracts import Tile

    return load_interface_class(
        folder / "handler.py",
        Tile,
        module_name=_module_name("tiles", tile_id),
    )
