"""Local secret store for connector API keys (gitignored YAML).

Connectors declare the env vars they need (a manifest's `auth.env`, e.g.
`BRAVE_API_KEY`). Rather than make the user export those in a shell, the board
lets them paste the value; we keep it in `secrets.local.yaml` (gitignored) and
apply it to the process environment, so a launched MCP server sees it exactly
like any other env var.

Values are secrets: they live only on disk locally and are never returned by the
API — endpoints report which env var *names* are set, never their values.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


class SecretStore:
    """Per-machine connector secrets (gitignored YAML). Env var name -> value."""

    def __init__(self, values: dict[str, str] | None = None, *, path: str | Path | None = None):
        self._values: dict[str, str] = dict(values or {})
        self._path = Path(path) if path else None

    @classmethod
    def load(cls, path: str | Path) -> SecretStore:
        p = Path(path)
        if not p.exists():
            return cls({}, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls({str(k): str(v) for k, v in data.items()}, path=p)

    def apply_to_env(self) -> None:
        """Seed stored secrets into the process environment. A var the user
        already exported wins at startup — `setdefault` won't clobber it."""
        for name, value in self._values.items():
            os.environ.setdefault(name, value)

    def set(self, name: str, value: str) -> None:
        """Store a secret and make it live immediately. An explicit UI set wins
        over any prior env value for this process."""
        self._values[name] = value
        os.environ[name] = value
        self._save()

    def remove(self, name: str) -> None:
        self._values.pop(name, None)
        os.environ.pop(name, None)
        self._save()

    def has(self, name: str) -> bool:
        return name in self._values

    def names(self) -> set[str]:
        return set(self._values)

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(yaml.safe_dump(self._values, sort_keys=False), encoding="utf-8")
