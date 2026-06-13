"""Request/response models for the REST API.

Kept separate from the app so the wire contract is readable in one place. None of
these carry secrets — provider views deliberately omit `api_key`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..contracts import Capability, Provider


class BrainView(BaseModel):
    """The brain a tile resolved to — what the board's brain badge renders."""

    source: str  # "default" | "pinned"
    label: str
    provider: str
    model: str
    endpoint: str | None = None


class TileSummary(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    connector: str | None
    permission_tier: str
    state: str
    allowed_tools: list[str]
    uses_default_brain: bool
    brain: BrainView | None = None
    needs_brain: bool = False  # true if no brain could be resolved (no default set)


class TileDetail(TileSummary):
    instructions: str
    provides: list[Capability]
    consumes: list[Capability]


class RunRequest(BaseModel):
    input: Any = None


class ExecutedView(BaseModel):
    tool: str
    ok: bool
    output: Any = None


class QueuedView(BaseModel):
    approval_id: str
    tool: str
    summary: str
    args: dict


class RejectedView(BaseModel):
    tool: str


class RunResponse(BaseModel):
    tile_id: str
    result: Any
    executed: list[ExecutedView]
    queued: list[QueuedView]
    rejected: list[RejectedView]


class ApprovalView(BaseModel):
    id: str
    tile_id: str
    tool: str
    args: dict
    summary: str
    side_effect: bool
    status: str
    output: Any = None


class ResolveRequest(BaseModel):
    approved: bool


class ProviderView(BaseModel):
    id: str
    kind: str
    provider: str | None = None
    endpoint: str | None = None
    model: str
    is_default: bool


class AddProviderRequest(BaseModel):
    provider: Provider
    make_default: bool = False


class SetDefaultRequest(BaseModel):
    provider_id: str


class PinBrainRequest(BaseModel):
    provider_id: str | None = None  # None clears the pin (back to default/manifest)


class TestResponse(BaseModel):
    ok: bool
    detail: str = ""
