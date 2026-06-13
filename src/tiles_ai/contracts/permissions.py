"""Permission tiers — the first-class safety layer of Tiles AI.

Every tile declares a `permission_tier`. Any action with a real-world side
effect (sending email, posting a message, writing to an external system)
defaults to human-in-the-loop. "Green" means *running*, not *unsupervised*.

The single source of truth for "what happens when a tile proposes an action"
is `evaluate()`. The permission gate (phase 3) is the only component that calls
it; the contract just defines the policy so the gate stays dumb and auditable.
"""

from __future__ import annotations

from enum import Enum


class PermissionTier(str, Enum):
    """How much autonomy a tile is granted over side-effectful actions."""

    READ_ONLY = "read_only"
    """May read/fetch from an app, never causes side effects.

    A `read_only` tile that proposes a side-effectful action is misbehaving —
    the gate rejects it rather than queuing it. This makes the tier a hard
    guarantee, not a polite request.
    """

    DRAFT = "draft"
    """Produces side-effectful actions, but they queue for human approval.

    Nothing fires until a human approves it. This is the default home for any
    tile that writes to the outside world.
    """

    AUTONOMOUS = "autonomous"
    """May execute approved side effects directly. Gated, opt-in.

    Even here, execution is expected to be explicitly opted into per tile — the
    tier permits autonomy, it does not assume it.
    """


class PermissionDecision(str, Enum):
    """What the gate decides to do with a single proposed action."""

    EXECUTE = "execute"
    """Run the action now."""

    QUEUE = "queue"
    """Hold the action in the approval queue for a human."""

    REJECT = "reject"
    """Refuse the action — it violates the tile's declared tier."""


# Human-readable tier descriptions, surfaced in docs and the board badge.
TIER_DESCRIPTIONS: dict[PermissionTier, str] = {
    PermissionTier.READ_ONLY: "Reads and reports. Never causes side effects.",
    PermissionTier.DRAFT: "Drafts side-effectful actions; queues them for approval.",
    PermissionTier.AUTONOMOUS: "May execute approved side effects directly (opt-in).",
}


def evaluate(
    tier: PermissionTier,
    is_side_effect: bool,
    *,
    approved: bool = False,
) -> PermissionDecision:
    """Decide the fate of one proposed action under a tile's permission tier.

    Args:
        tier: the tile's declared permission tier.
        is_side_effect: whether the action touches the outside world. The
            connector is the authority on this flag (a tool declares whether it
            is side-effectful); the gate trusts it.
        approved: whether a human has already approved this specific action.
            Only meaningful for `autonomous` tiles in v0.

    Policy:
        * A non-side-effectful action always EXECUTEs, regardless of tier.
        * read_only + side effect            -> REJECT (tier violation)
        * draft     + side effect            -> QUEUE  (await human)
        * autonomous + side effect + approved -> EXECUTE
        * autonomous + side effect + !approved -> QUEUE (opt-in gate)
    """
    if not is_side_effect:
        return PermissionDecision.EXECUTE

    if tier is PermissionTier.READ_ONLY:
        return PermissionDecision.REJECT

    if tier is PermissionTier.DRAFT:
        return PermissionDecision.QUEUE

    # autonomous
    return PermissionDecision.EXECUTE if approved else PermissionDecision.QUEUE
