"""The event stream — a tiny in-process pub/sub the board subscribes to.

The runtime publishes lifecycle and action events (activated, run, queued,
executed, rejected, approval resolved); the API's SSE endpoint subscribes a
queue and forwards them to the board's live activity feed. Deliberately minimal:
no persistence, no ordering guarantees beyond per-subscriber FIFO, no backlog —
a subscriber sees events from the moment it subscribes.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class Event:
    """One thing that happened, fanned out to every live subscriber."""

    type: str
    tile_id: str | None = None
    data: dict = field(default_factory=dict)
    ts: float | None = None  # set by the bus on publish if unset


class EventBus:
    """In-process fan-out to any number of async subscriber queues."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def publish(self, event: Event) -> None:
        """Deliver an event to every current subscriber (non-blocking)."""
        if event.ts is None:
            event.ts = time.time()
        for q in list(self._subscribers):
            q.put_nowait(event)

    def subscribe(self) -> "asyncio.Queue[Event]":
        """Register a new subscriber queue. Caller must unsubscribe when done."""
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[Event]") -> None:
        self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


__all__ = ["Event", "EventBus"]
