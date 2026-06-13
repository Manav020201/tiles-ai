"""Tiles AI — the tile contract.

This package is the spine of the project. The board, the runtime, the docs, and
future multi-tile collaboration are all downstream of the types defined here.
SPEC.md is the prose companion; these modules are the executable truth.

Exports are grouped by concern:
  * manifests   — ConnectorManifest, TileManifest, ModelRef, ...
  * brain       — BrainConfig, providers, resolve_brain, ResolvedBrain
  * interfaces  — Connector, Tile, and their I/O types
  * lifecycle   — TileState + transition rules
  * permissions — PermissionTier + the gate's decision policy
  * validation  — cross-manifest checks + manifest loaders
"""

from __future__ import annotations

from .connector import (
    CallContext,
    Connector,
    Session,
    ToolResult,
)
from .connector_manifest import (
    AuthConfig,
    ConnectorKind,
    ConnectorManifest,
    ToolSpec,
)
from .lifecycle import (
    InvalidTransition,
    TileState,
    can_transition,
    legal_transitions,
    transition,
)
from .permissions import (
    TIER_DESCRIPTIONS,
    PermissionDecision,
    PermissionTier,
    evaluate,
)
from .provider_config import (
    BrainConfig,
    BrainResolutionError,
    HostedProvider,
    LocalProvider,
    ProviderKind,
    ResolvedBrain,
    resolve_brain,
)
from .tile import (
    ActionPlan,
    ProposedAction,
    RunContext,
    Tile,
    ValidationResult,
)
from .tile_manifest import Capability, ModelRef, TileManifest
from .validation import (
    ContractError,
    assert_tile_valid,
    load_connector_manifest,
    load_tile_manifest,
    validate_tile_against_connector,
)

__all__ = [
    # manifests
    "ConnectorManifest",
    "ConnectorKind",
    "AuthConfig",
    "ToolSpec",
    "TileManifest",
    "ModelRef",
    "Capability",
    # brain
    "BrainConfig",
    "ProviderKind",
    "HostedProvider",
    "LocalProvider",
    "ResolvedBrain",
    "resolve_brain",
    "BrainResolutionError",
    # interfaces
    "Connector",
    "Session",
    "ToolResult",
    "CallContext",
    "Tile",
    "ActionPlan",
    "ProposedAction",
    "RunContext",
    "ValidationResult",
    # lifecycle
    "TileState",
    "can_transition",
    "transition",
    "legal_transitions",
    "InvalidTransition",
    # permissions
    "PermissionTier",
    "PermissionDecision",
    "evaluate",
    "TIER_DESCRIPTIONS",
    # validation
    "validate_tile_against_connector",
    "assert_tile_valid",
    "load_connector_manifest",
    "load_tile_manifest",
    "ContractError",
]
