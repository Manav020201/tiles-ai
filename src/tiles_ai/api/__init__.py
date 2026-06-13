"""The HTTP control-plane API (FastAPI) + SSE event stream.

`create_app(root=..., brain_store=..., model_adapter=...)` returns a FastAPI app
wired to a board. See SPEC.md "Build order" phase 4.
"""

from __future__ import annotations

from .app import create_app, format_sse

__all__ = ["create_app", "format_sse"]
