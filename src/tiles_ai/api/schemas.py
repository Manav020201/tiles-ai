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
    wants_input: bool = False  # true if the tile takes a freeform text input
    input_hint: str | None = None  # placeholder for that input, if any
    input_optional: bool = False  # true if the input can be left blank
    connector_ready: bool = True  # false if the connector is missing required env
    missing_env: list[str] = []  # env vars the connector needs but that aren't set
    schedule: str | None = None  # interval like "5m" if the tile auto-runs


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


class UsageView(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class RunResponse(BaseModel):
    tile_id: str
    result: Any
    executed: list[ExecutedView]
    queued: list[QueuedView]
    rejected: list[RejectedView]
    usage: UsageView | None = None  # tokens this run consumed


class FlowRunRequest(BaseModel):
    tiles: list[str]  # run in order; each result feeds the next
    input: Any = None


class FlowStepView(BaseModel):
    tile_id: str
    result: Any
    queued: int
    executed: int
    rejected: int


class FlowRunResponse(BaseModel):
    steps: list[FlowStepView]


class FlowCandidatesView(BaseModel):
    feeds: list[str]  # tiles this one can feed into (its provides ∩ their consumes)
    fed_by: list[str]  # tiles that can feed this one


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


class ConnectorToolView(BaseModel):
    name: str
    description: str
    side_effect: bool


class ConnectorView(BaseModel):
    id: str
    app: str
    kind: str
    endpoint: str | None = None
    env: list[str] = []  # env var names this connector needs
    missing_env: list[str] = []  # of those, the ones with no value set yet
    oauth: bool = False  # the connector declares an OAuth flow
    oauth_client_id: str | None = None  # the OAuth client id (public; editable)
    authorized: bool = False  # a token has been stored
    tools: list[ConnectorToolView]


class SetSecretsRequest(BaseModel):
    # Map of env var name -> value (e.g. {"BRAVE_API_KEY": "..."}). Stored locally
    # in secrets.local.yaml and applied to the process env; never echoed back.
    values: dict[str, str]


class CreateConnectorRequest(BaseModel):
    app: str
    id: str | None = None  # derived from app if omitted
    kind: str = "mcp"  # mcp | mock
    endpoint: str | None = None  # MCP server command (required for kind=mcp)
    env: list[str] = []  # names of env vars the server needs
    tools: list[ConnectorToolView] = []


class UpdateConnectorRequest(BaseModel):
    app: str | None = None
    endpoint: str | None = None
    env: list[str] | None = None
    oauth_client_id: str | None = None  # set the OAuth client id (for oauth2 connectors)
    tools: list[ConnectorToolView] | None = None


class IntrospectRequest(BaseModel):
    endpoint: str
    env: list[str] = []


class LoadErrorView(BaseModel):
    kind: str  # "connector" | "tile"
    source: str
    errors: list[str]


class UpdateTileRequest(BaseModel):
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    instructions: str | None = None
    permission_tier: str | None = None
    wants_input: bool | None = None
    input_hint: str | None = None
    schedule: str | None = None  # "" clears it; e.g. "5m"


class ScheduledTileView(BaseModel):
    tile_id: str
    every: str
    interval_seconds: int


class CreateTileRequest(BaseModel):
    name: str
    id: str | None = None  # derived from name if omitted
    icon: str = "🔲"
    description: str = "One line shown on the board."
    instructions: str = "The system prompt / role for this tile's agent."
    permission_tier: str = "read_only"
    connector: str | None = None  # omit for an instant tile
    allowed_tools: list[str] = []
    wants_input: bool = True
    input_hint: str | None = None
    schedule: str | None = None  # interval like "5m" to auto-run
