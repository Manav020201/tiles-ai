"""The FastAPI control-plane API + SSE event stream.

`create_app` wires a board into an HTTP surface: discover the registry, hold a
brain store + model adapter + runtime + event bus, and expose endpoints to list
tiles, activate/deactivate/run them, resolve approvals, manage providers, and
stream live events to the board.

The app is dependency-injectable: tests pass an offline (echo) model adapter and
a fixture root, so the whole API runs without a network or real keys.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..contracts import (
    BrainResolutionError,
    HostedProvider,
    LocalProvider,
    ResolvedBrain,
)
from ..events import Event, EventBus
from ..model import BrainStore, ModelAdapter
from ..registry import Registry
from ..runtime import Runtime, RuntimeError_
from .schemas import (
    AddProviderRequest,
    ApprovalView,
    BrainView,
    ExecutedView,
    PinBrainRequest,
    ProviderView,
    QueuedView,
    RejectedView,
    ResolveRequest,
    RunRequest,
    RunResponse,
    SetDefaultRequest,
    TestResponse,
    TileDetail,
    TileSummary,
)


def create_app(
    *,
    root: str | Path | None = None,
    brain_store: BrainStore | None = None,
    model_adapter: ModelAdapter | None = None,
) -> FastAPI:
    root = Path(root) if root else Path.cwd()
    registry = Registry.discover(root)
    store = brain_store or BrainStore()
    adapter = model_adapter or ModelAdapter(store)
    bus = EventBus()
    runtime = Runtime(registry, adapter, events=bus)

    app = FastAPI(title="Tiles AI", version=__version__)
    app.state.registry = registry
    app.state.store = store
    app.state.adapter = adapter
    app.state.bus = bus
    app.state.runtime = runtime

    # --- helpers -----------------------------------------------------------

    def _brain_view(resolved: ResolvedBrain) -> BrainView:
        return BrainView(
            source=resolved.source,
            label=resolved.badge_label,
            provider=resolved.provider,
            model=resolved.model,
            endpoint=resolved.endpoint,
        )

    def _tile_summary(tile_id: str) -> TileSummary:
        loaded = registry.get_tile(tile_id)
        if loaded is None:
            raise HTTPException(404, f"no tile '{tile_id}'")
        m = loaded.manifest
        brain: BrainView | None = None
        needs_brain = False
        uses_default = m.uses_default_brain()
        try:
            resolved = runtime.resolve_brain_for(m.id)
            brain = _brain_view(resolved)
            uses_default = resolved.source == "default"
        except BrainResolutionError:
            needs_brain = True
        wants_input = len(m.consumes) > 0
        input_hint = (m.consumes[0].description or m.consumes[0].name) if wants_input else None

        # Connector readiness: which required env vars (if any) aren't set yet.
        missing_env: list[str] = []
        if m.connector:
            lc = registry.get_connector(m.connector)
            if lc is not None:
                missing_env = [e for e in lc.manifest.auth.env if not os.environ.get(e)]

        return TileSummary(
            id=m.id,
            name=m.name,
            description=m.description,
            icon=m.icon,
            connector=m.connector,
            permission_tier=m.permission_tier.value,
            state=runtime.state(m.id).value,
            allowed_tools=m.allowed_tools,
            uses_default_brain=uses_default,
            brain=brain,
            needs_brain=needs_brain,
            wants_input=wants_input,
            input_hint=input_hint,
            connector_ready=not missing_env,
            missing_env=missing_env,
        )

    def _provider_view(provider) -> ProviderView:
        is_default = provider.id == store.config.default_provider
        if isinstance(provider, HostedProvider):
            return ProviderView(
                id=provider.id,
                kind="hosted",
                provider=provider.provider,
                model=provider.model,
                is_default=is_default,
            )
        assert isinstance(provider, LocalProvider)
        return ProviderView(
            id=provider.id,
            kind="local",
            endpoint=provider.endpoint,
            model=provider.model,
            is_default=is_default,
        )

    # --- tiles -------------------------------------------------------------

    @app.get("/api/tiles", response_model=list[TileSummary])
    def list_tiles() -> list[TileSummary]:
        return [_tile_summary(tid) for tid in sorted(registry.tiles)]

    @app.get("/api/tiles/{tile_id}", response_model=TileDetail)
    def get_tile(tile_id: str) -> TileDetail:
        summary = _tile_summary(tile_id)
        m = registry.get_tile(tile_id).manifest
        return TileDetail(
            **summary.model_dump(),
            instructions=m.instructions,
            provides=m.provides,
            consumes=m.consumes,
        )

    @app.post("/api/tiles/{tile_id}/activate", response_model=TileSummary)
    async def activate(tile_id: str) -> TileSummary:
        try:
            await runtime.activate(tile_id)
        except RuntimeError_ as exc:
            raise HTTPException(404, str(exc)) from exc
        except BrainResolutionError as exc:
            raise HTTPException(409, str(exc)) from exc  # connect a brain first
        return _tile_summary(tile_id)

    @app.post("/api/tiles/{tile_id}/deactivate", response_model=TileSummary)
    async def deactivate(tile_id: str) -> TileSummary:
        await runtime.deactivate(tile_id)
        return _tile_summary(tile_id)

    @app.put("/api/tiles/{tile_id}/brain", response_model=TileSummary)
    def pin_brain(tile_id: str, body: PinBrainRequest) -> TileSummary:
        if registry.get_tile(tile_id) is None:
            raise HTTPException(404, f"no tile '{tile_id}'")
        if body.provider_id is not None and store.config.get(body.provider_id) is None:
            raise HTTPException(404, f"no provider '{body.provider_id}'")
        runtime.set_brain_override(tile_id, body.provider_id)
        return _tile_summary(tile_id)

    @app.post("/api/tiles/{tile_id}/run", response_model=RunResponse)
    async def run(tile_id: str, body: RunRequest | None = None) -> RunResponse:
        try:
            outcome = await runtime.run(tile_id, body.input if body else None)
        except RuntimeError_ as exc:
            raise HTTPException(409, str(exc)) from exc  # not active
        return RunResponse(
            tile_id=outcome.tile_id,
            result=outcome.result,
            executed=[
                ExecutedView(tool=e.action.tool, ok=e.result.ok, output=e.result.output)
                for e in outcome.gate.executed
            ],
            queued=[
                QueuedView(
                    approval_id=q.id,
                    tool=q.action.tool,
                    summary=q.action.summary,
                    args=q.action.args,
                )
                for q in outcome.gate.queued
            ],
            rejected=[RejectedView(tool=a.tool) for a in outcome.gate.rejected],
        )

    # --- approvals ---------------------------------------------------------

    def _approval_view(item) -> ApprovalView:
        return ApprovalView(
            id=item.id,
            tile_id=item.tile_id,
            tool=item.action.tool,
            args=item.action.args,
            summary=item.action.summary,
            side_effect=item.action.side_effect,
            status=item.status.value,
            output=item.result.output if item.result else None,
        )

    @app.get("/api/approvals", response_model=list[ApprovalView])
    def list_approvals(tile_id: str | None = None) -> list[ApprovalView]:
        return [_approval_view(i) for i in runtime.pending_approvals(tile_id)]

    @app.post("/api/approvals/{approval_id}/resolve", response_model=ApprovalView)
    async def resolve_approval(approval_id: str, body: ResolveRequest) -> ApprovalView:
        try:
            item = await runtime.resolve_approval(approval_id, body.approved)
        except RuntimeError_ as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc  # already resolved
        return _approval_view(item)

    # --- providers (the brain layer) --------------------------------------

    @app.get("/api/providers", response_model=list[ProviderView])
    def list_providers() -> list[ProviderView]:
        return [_provider_view(p) for p in store.config.providers]

    @app.post("/api/providers", response_model=list[ProviderView])
    def add_provider(body: AddProviderRequest) -> list[ProviderView]:
        store.add_provider(body.provider, make_default=body.make_default)
        return [_provider_view(p) for p in store.config.providers]

    @app.put("/api/brain/default", response_model=list[ProviderView])
    def set_default(body: SetDefaultRequest) -> list[ProviderView]:
        if store.config.get(body.provider_id) is None:
            raise HTTPException(404, f"no provider '{body.provider_id}'")
        store.set_default(body.provider_id)
        return [_provider_view(p) for p in store.config.providers]

    @app.post("/api/providers/{provider_id}/test", response_model=TestResponse)
    async def test_provider(provider_id: str) -> TestResponse:
        result = await adapter.test(provider_id)
        return TestResponse(ok=result.ok, detail=result.detail)

    # --- events (SSE) ------------------------------------------------------

    @app.get("/api/events")
    async def events(request: Request) -> StreamingResponse:
        return StreamingResponse(_event_stream(bus, request), media_type="text/event-stream")

    # Serve the built board at the root, mounted last so the /api routes take
    # precedence. Prefer a freshly-built dev board (frontend/dist under the board
    # root); fall back to the board bundled in the installed package (populated by
    # the release build). So both `npm run build` + dev and `pipx install` work.
    board = _board_dir(Path(root))
    if board is not None:
        app.mount("/", StaticFiles(directory=str(board), html=True), name="board")

    return app


def _board_dir(root: Path) -> Path | None:
    dev = root / "frontend" / "dist"
    if dev.is_dir():
        return dev
    packaged = Path(__file__).resolve().parent.parent / "web"
    if packaged.is_dir() and (packaged / "index.html").is_file():
        return packaged
    return None


def format_sse(event: Event) -> str:
    """Render an event as a Server-Sent-Events frame."""
    payload = {
        "type": event.type,
        "tile_id": event.tile_id,
        "data": event.data,
        "ts": event.ts,
    }
    return f"event: {event.type}\ndata: {json.dumps(payload)}\n\n"


async def _event_stream(bus: EventBus, request: Request):
    """Yield SSE frames for each event until the client disconnects."""
    q = bus.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                yield format_sse(event)
            except TimeoutError:
                yield ": keepalive\n\n"  # comment frame keeps the connection warm
    finally:
        bus.unsubscribe(q)
