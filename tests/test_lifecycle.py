import pytest

from tiles_ai.contracts import (
    InvalidTransition,
    TileState,
    can_transition,
    legal_transitions,
    transition,
)


def test_happy_path_progression():
    assert can_transition(TileState.DEFINED, TileState.AVAILABLE)
    assert can_transition(TileState.AVAILABLE, TileState.ACTIVE)
    assert can_transition(TileState.ACTIVE, TileState.PAUSED)
    assert can_transition(TileState.ACTIVE, TileState.STOPPED)
    assert can_transition(TileState.PAUSED, TileState.ACTIVE)
    assert can_transition(TileState.STOPPED, TileState.AVAILABLE)


def test_illegal_transitions_rejected():
    # Cannot activate something never loaded.
    assert not can_transition(TileState.DEFINED, TileState.ACTIVE)
    # Cannot jump straight from available to paused.
    assert not can_transition(TileState.AVAILABLE, TileState.PAUSED)


def test_transition_guard_raises_with_message():
    with pytest.raises(InvalidTransition) as exc:
        transition(TileState.DEFINED, TileState.ACTIVE)
    assert "defined" in str(exc.value)
    assert "available" in str(exc.value)  # tells you the legal next step


def test_transition_returns_target_when_legal():
    assert transition(TileState.AVAILABLE, TileState.ACTIVE) is TileState.ACTIVE


def test_composed_is_reserved_unreachable():
    # No state transitions *into* composed in v0.
    for state in TileState:
        assert not can_transition(state, TileState.COMPOSED)
    # And composed has no outbound edges.
    assert legal_transitions(TileState.COMPOSED) == frozenset()
