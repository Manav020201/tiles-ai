"""The scheduler — runs tiles that declare an interval `schedule`.

A tile with `schedule: { every: "5m" }` is activated and run automatically on
that cadence. The scheduler reads the registry each tick, so schedules added or
edited at runtime (rescan) are picked up without a restart. It is deliberately
small: interval-only, in-process, best-effort (a failing tile doesn't kill the
loop). Cron and event triggers are a later extension.

`tick(now)` is pure-ish and unit-testable; `start()`/`stop()` run the background
loop (wired into the API's lifespan).
"""

from __future__ import annotations

import asyncio
import contextlib
import time

from .runtime import Runtime


class Scheduler:
    def __init__(self, runtime: Runtime, *, poll_seconds: float = 1.0) -> None:
        self.runtime = runtime
        self._poll = poll_seconds
        self._last_run: dict[str, float] = {}
        self._task: asyncio.Task | None = None

    def _scheduled(self) -> dict[str, int]:
        """tile_id -> interval seconds, for every tile that declares a schedule."""
        return {
            tid: lt.manifest.schedule.interval_seconds()
            for tid, lt in self.runtime.registry.tiles.items()
            if lt.manifest.schedule is not None
        }

    def due(self, now: float) -> list[str]:
        """Tile ids whose interval has elapsed since their last scheduled run."""
        due = []
        for tid, interval in self._scheduled().items():
            last = self._last_run.get(tid)
            if last is None or (now - last) >= interval:
                due.append(tid)
        return due

    async def tick(self, now: float) -> list[str]:
        """Run every due tile once. Returns the ids that ran."""
        ran = []
        for tid in self.due(now):
            self._last_run[tid] = now
            try:
                await self.runtime.run_scheduled(tid)
                ran.append(tid)
            except Exception:  # noqa: BLE001 - one bad tile must not kill the loop
                continue
        return ran

    def prime(self, now: float) -> None:
        """Mark all current schedules as just-run, so none fires immediately."""
        for tid in self._scheduled():
            self._last_run[tid] = now

    async def start(self) -> None:
        self.prime(time.monotonic())  # don't fire everything on boot
        self._task = asyncio.ensure_future(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll)
            await self.tick(time.monotonic())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
