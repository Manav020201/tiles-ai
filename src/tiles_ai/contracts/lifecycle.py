"""Tile lifecycle — the state machine every tile moves through.

A tile is born as a `defined` manifest on disk and is promoted to `available`
once the registry validates and loads it. The user activates it (`active` =
green on the board), and may `pause` or `stop` it. `composed` is reserved for
future multi-tile collaboration and is intentionally left unwired in v0 — it
exists here only so the rest of the system does not paint itself into a corner.

This module is pure data + pure functions: no I/O, no framework. The runtime
(phase 3) owns *which* transition happens; this module owns *whether* it is
legal.
"""

from __future__ import annotations

from enum import Enum


class TileState(str, Enum):
    """The states a tile can occupy.

    Ordered roughly by lifecycle progression. `str` mixin so a state
    serializes to its name in JSON/manifests without extra encoders.
    """

    DEFINED = "defined"
    """Manifest exists on disk; not yet validated or loaded."""

    AVAILABLE = "available"
    """Validated, dependencies satisfied, loaded by the registry, idle."""

    ACTIVE = "active"
    """User activated it (green); the runtime is executing/listening."""

    PAUSED = "paused"
    """Temporarily suspended; resources may still be held. Resumable."""

    STOPPED = "stopped"
    """Deactivated and torn down. Can be made available again."""

    COMPOSED = "composed"
    """RESERVED for multi-tile collaboration (v0: never entered)."""


# Allowed transitions. Source state -> set of legal destination states.
# `COMPOSED` is intentionally unreachable in v0 (no edges into it) but is a
# declared key so future work has an obvious, single place to wire it in.
_TRANSITIONS: dict[TileState, frozenset[TileState]] = {
    TileState.DEFINED: frozenset({TileState.AVAILABLE}),
    TileState.AVAILABLE: frozenset({TileState.ACTIVE}),
    TileState.ACTIVE: frozenset({TileState.PAUSED, TileState.STOPPED}),
    TileState.PAUSED: frozenset({TileState.ACTIVE, TileState.STOPPED}),
    TileState.STOPPED: frozenset({TileState.AVAILABLE}),
    TileState.COMPOSED: frozenset(),  # reserved — no outbound edges yet
}


def can_transition(current: TileState, target: TileState) -> bool:
    """Return True if moving from `current` to `target` is legal."""
    return target in _TRANSITIONS[current]


def transition(current: TileState, target: TileState) -> TileState:
    """Return `target` if the transition is legal, else raise.

    The runtime calls this as a guard before mutating activation state, so an
    illegal request (e.g. activating a tile that was never loaded) fails loudly
    with an actionable message instead of silently corrupting state.
    """
    if not can_transition(current, target):
        allowed = ", ".join(sorted(s.value for s in _TRANSITIONS[current])) or "(none)"
        raise InvalidTransition(
            f"Cannot move tile from '{current.value}' to '{target.value}'. "
            f"Legal transitions from '{current.value}': {allowed}."
        )
    return target


def legal_transitions(current: TileState) -> frozenset[TileState]:
    """Return the set of states reachable from `current` in one step."""
    return _TRANSITIONS[current]


class InvalidTransition(Exception):
    """Raised when an illegal lifecycle transition is attempted."""
