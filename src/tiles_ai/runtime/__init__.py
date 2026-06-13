"""The runtime layer — activation, execution, permission gating, approvals.

`Runtime` drives tiles through their lifecycle and routes proposed actions
through the `PermissionGate`. Handlers receive a `RunContext` carrying a
`ToolProxy` (`ctx.tools`) and a `ModelHandle` (`ctx.model`).
"""

from __future__ import annotations

from .gate import (
    ApprovalItem,
    ApprovalStatus,
    GateOutcome,
    PermissionGate,
)
from .handles import ModelHandle, ToolDenied, ToolProxy
from .runtime import ActiveTile, RunOutcome, Runtime, RuntimeError_

__all__ = [
    "Runtime",
    "RuntimeError_",
    "ActiveTile",
    "RunOutcome",
    "PermissionGate",
    "GateOutcome",
    "ApprovalItem",
    "ApprovalStatus",
    "ToolProxy",
    "ToolDenied",
    "ModelHandle",
]
