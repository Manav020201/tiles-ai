"""Scheduled triggers: interval parsing + the scheduler's due/tick logic."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tiles_ai.api import create_app
from tiles_ai.contracts import HostedProvider, Schedule
from tiles_ai.model import BrainStore, ModelAdapter, echo_client_factory
from tiles_ai.registry import Registry
from tiles_ai.runtime import Runtime, Scheduler
from tiles_ai.scaffold import scaffold_tile

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_schedule_interval_parsing():
    assert Schedule(every="30s").interval_seconds() == 30
    assert Schedule(every="5m").interval_seconds() == 300
    assert Schedule(every="2h").interval_seconds() == 7200
    assert Schedule(every="1d").interval_seconds() == 86400


def test_schedule_rejects_bad_interval():
    with pytest.raises(ValueError):
        Schedule(every="soon")


def _scheduled_runtime(tmp_path):
    scaffold_tile(tmp_path, id="cron", name="Cron", instructions="x", schedule="1m")
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="c", provider="anthropic", api_key="k", model="claude-opus-4-8"),
        make_default=True,
    )
    reg = Registry.discover(tmp_path)
    assert reg.ok, reg.report()
    return Runtime(reg, ModelAdapter(store, client_factory=echo_client_factory))


def test_scheduler_runs_due_tiles_and_respects_interval(tmp_path):
    rt = _scheduled_runtime(tmp_path)
    sched = Scheduler(rt)

    async def go():
        # First tick: tile is due (never run) -> runs.
        ran1 = await sched.tick(now=1000.0)
        # 30s later: not due (interval is 60s).
        ran2 = await sched.tick(now=1030.0)
        # 60s after the first run: due again.
        ran3 = await sched.tick(now=1061.0)
        return ran1, ran2, ran3

    ran1, ran2, ran3 = asyncio.run(go())
    assert ran1 == ["cron"]
    assert ran2 == []
    assert ran3 == ["cron"]
    assert rt.is_active("cron")  # scheduled run activated it


def test_scheduler_prime_skips_immediate_fire(tmp_path):
    rt = _scheduled_runtime(tmp_path)
    sched = Scheduler(rt)
    sched.prime(now=1000.0)  # what start() does

    async def go():
        return await sched.tick(now=1001.0)  # only 1s later -> not due

    assert asyncio.run(go()) == []


def test_schedules_endpoint_and_create_with_schedule(tmp_path):
    # Temp board so creating writes there.
    (tmp_path / "tiles").mkdir()
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="c", provider="anthropic", api_key="k", model="claude-opus-4-8"),
        make_default=True,
    )
    app = create_app(
        root=tmp_path,
        brain_store=store,
        model_adapter=ModelAdapter(store, client_factory=echo_client_factory),
    )
    client = TestClient(app)
    resp = client.post("/api/tiles", json={"name": "Heartbeat", "schedule": "10m"})
    assert resp.status_code == 201 and resp.json()["schedule"] == "10m"
    schedules = client.get("/api/schedules").json()
    assert any(s["tile_id"] == "heartbeat" and s["interval_seconds"] == 600 for s in schedules)
