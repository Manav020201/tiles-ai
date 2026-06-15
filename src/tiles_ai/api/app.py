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
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..connectors import MCPError
from ..connectors import introspect as introspect_mcp
from ..contracts import (
    BrainResolutionError,
    HostedProvider,
    LocalProvider,
    ResolvedBrain,
    TileManifest,
    validate_tile_against_connector,
)
from ..events import Event, EventBus
from ..model import BrainStore, ModelAdapter, ModelClientError
from ..oauth import OAuthError, TokenStore, build_authorize_url, exchange_code
from ..registry import Registry
from ..runtime import Runtime, RuntimeError_, Scheduler
from ..scaffold import (
    ScaffoldError,
    build_manifest,
    delete_connector,
    delete_tile,
    scaffold_connector,
    scaffold_tile,
    slugify,
    update_connector,
    update_tile,
)
from ..secrets import SecretStore
from .schemas import (
    AddProviderRequest,
    ApprovalView,
    BrainView,
    ConnectorToolView,
    ConnectorView,
    CreateConnectorRequest,
    CreateTileRequest,
    ExecutedView,
    FlowCandidatesView,
    FlowRunRequest,
    FlowRunResponse,
    FlowStepView,
    IntrospectRequest,
    LoadErrorView,
    PinBrainRequest,
    ProviderView,
    QueuedView,
    RejectedView,
    ResolveRequest,
    RunRequest,
    RunResponse,
    ScheduledTileView,
    SetDefaultRequest,
    SetSecretsRequest,
    TestResponse,
    TileDetail,
    TileSummary,
    UpdateConnectorRequest,
    UpdateTileRequest,
)


def create_app(
    *,
    root: str | Path | None = None,
    brain_store: BrainStore | None = None,
    model_adapter: ModelAdapter | None = None,
    token_store: TokenStore | None = None,
) -> FastAPI:
    root = Path(root) if root else Path.cwd()
    registry = Registry.discover(root)
    store = brain_store or BrainStore()
    adapter = model_adapter or ModelAdapter(store)
    tokens = token_store or TokenStore.load(root / "oauth.local.yaml")
    # Connector API keys entered from the board, applied to the process env so
    # launched MCP servers see them. (Named to avoid the stdlib `secrets` import.)
    secret_store = SecretStore.load(root / "secrets.local.yaml")
    secret_store.apply_to_env()
    bus = EventBus()
    runtime = Runtime(registry, adapter, events=bus, token_store=tokens)
    scheduler = Scheduler(runtime)
    oauth_states: dict[str, str] = {}  # short-lived: state -> connector id

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await scheduler.start()  # run tiles that declare an interval schedule
        try:
            yield
        finally:
            await scheduler.stop()

    app = FastAPI(title="Tiles AI", version=__version__, lifespan=lifespan)
    app.state.registry = registry
    app.state.store = store
    app.state.adapter = adapter
    app.state.bus = bus
    app.state.runtime = runtime
    app.state.scheduler = scheduler
    app.state.tokens = tokens

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
            schedule=m.schedule.every if m.schedule else None,
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

    def _connector_view(cid: str) -> ConnectorView:
        m = registry.connectors[cid].manifest
        return ConnectorView(
            id=m.id,
            app=m.app,
            kind=m.kind.value,
            endpoint=m.endpoint,
            env=m.auth.env,
            missing_env=[e for e in m.auth.env if not os.environ.get(e)],
            oauth=m.auth.oauth is not None,
            authorized=tokens.is_authorized(cid),
            tools=[
                ConnectorToolView(name=t.name, description=t.description, side_effect=t.side_effect)
                for t in m.tools
            ],
        )

    @app.get("/api/connectors", response_model=list[ConnectorView])
    def list_connectors() -> list[ConnectorView]:
        # Lets the board's "create tile" form offer a connector + its tools.
        return [_connector_view(cid) for cid in sorted(registry.connectors)]

    @app.post("/api/connectors/introspect", response_model=list[ConnectorToolView])
    async def introspect_connector(body: IntrospectRequest) -> list[ConnectorToolView]:
        # Launch an MCP server and read its tools so the form can prefill them.
        try:
            tools = await introspect_mcp(body.endpoint, body.env)
        except MCPError as exc:
            raise HTTPException(400, str(exc)) from exc
        return [
            ConnectorToolView(name=t.name, description=t.description, side_effect=t.side_effect)
            for t in tools
        ]

    @app.post("/api/connectors", response_model=ConnectorView, status_code=201)
    def create_connector(body: CreateConnectorRequest) -> ConnectorView:
        cid = body.id or slugify(body.app)
        try:
            scaffold_connector(
                root,
                id=cid,
                app=body.app,
                kind=body.kind,
                endpoint=body.endpoint,
                env=body.env,
                tools=[t.model_dump() for t in body.tools],
            )
        except ScaffoldError as exc:
            raise HTTPException(400, str(exc)) from exc
        registry.rescan(root)
        return _connector_view(cid)

    @app.put("/api/connectors/{connector_id}", response_model=ConnectorView)
    def edit_connector(connector_id: str, body: UpdateConnectorRequest) -> ConnectorView:
        if registry.get_connector(connector_id) is None:
            raise HTTPException(404, f"no connector '{connector_id}'")
        changes = body.model_dump()
        if changes.get("tools") is not None:
            changes["tools"] = [t.model_dump() for t in body.tools]
        try:
            update_connector(root, connector_id, changes)
        except ScaffoldError as exc:
            raise HTTPException(400, str(exc)) from exc
        registry.rescan(root)
        return _connector_view(connector_id)

    @app.delete("/api/connectors/{connector_id}")
    def remove_connector(connector_id: str) -> dict:
        if registry.get_connector(connector_id) is None:
            raise HTTPException(404, f"no connector '{connector_id}'")
        bound = [t.id for t in registry.tiles_for_connector(connector_id)]
        if bound:
            raise HTTPException(
                409, f"'{connector_id}' is used by tiles {bound} — remove those first."
            )
        tokens.remove(connector_id)
        delete_connector(root, connector_id)
        registry.rescan(root)
        return {"deleted": connector_id}

    @app.put("/api/connectors/{connector_id}/secrets", response_model=ConnectorView)
    def set_connector_secrets(connector_id: str, body: SetSecretsRequest) -> ConnectorView:
        lc = registry.get_connector(connector_id)
        if lc is None:
            raise HTTPException(404, f"no connector '{connector_id}'")
        allowed = set(lc.manifest.auth.env)
        unknown = [name for name in body.values if name not in allowed]
        if unknown:
            raise HTTPException(400, f"connector '{connector_id}' has no env var(s) {unknown}")
        for name, value in body.values.items():
            if value.strip():
                secret_store.set(name, value.strip())
        return _connector_view(connector_id)

    @app.delete("/api/connectors/{connector_id}/secrets/{name}", response_model=ConnectorView)
    def clear_connector_secret(connector_id: str, name: str) -> ConnectorView:
        lc = registry.get_connector(connector_id)
        if lc is None:
            raise HTTPException(404, f"no connector '{connector_id}'")
        if name not in set(lc.manifest.auth.env):
            raise HTTPException(400, f"connector '{connector_id}' has no env var '{name}'")
        secret_store.remove(name)
        return _connector_view(connector_id)

    # --- OAuth (authorization-code) ----------------------------------------

    @app.get("/api/connectors/{connector_id}/oauth/start")
    def oauth_start(connector_id: str, request: Request) -> dict:
        lc = registry.get_connector(connector_id)
        if lc is None:
            raise HTTPException(404, f"no connector '{connector_id}'")
        oauth = lc.manifest.auth.oauth
        if oauth is None:
            raise HTTPException(400, f"connector '{connector_id}' has no OAuth config")
        state = secrets.token_urlsafe(24)
        oauth_states[state] = connector_id
        redirect_uri = str(request.base_url).rstrip("/") + "/api/oauth/callback"
        return {"authorize_url": build_authorize_url(oauth, redirect_uri, state)}

    @app.get("/api/oauth/callback", response_class=HTMLResponse)
    async def oauth_callback(
        request: Request, code: str = "", state: str = "", error: str = ""
    ) -> str:
        if error:
            return f"<p>Authorization failed: {error}. You can close this window.</p>"
        connector_id = oauth_states.pop(state, None)
        if connector_id is None:
            raise HTTPException(400, "invalid or expired OAuth state")
        lc = registry.get_connector(connector_id)
        if lc is None or lc.manifest.auth.oauth is None:
            raise HTTPException(404, "connector no longer has OAuth config")
        oauth = lc.manifest.auth.oauth
        secret = os.environ.get(oauth.client_secret_env) if oauth.client_secret_env else None
        redirect_uri = str(request.base_url).rstrip("/") + "/api/oauth/callback"
        try:
            token = await exchange_code(
                oauth, code=code, redirect_uri=redirect_uri, client_secret=secret
            )
        except OAuthError as exc:
            raise HTTPException(400, str(exc)) from exc
        tokens.set(connector_id, token)
        return f"<p>Connected <b>{lc.manifest.app}</b>. You can close this window.</p>"

    @app.post("/api/connectors/{connector_id}/oauth/disconnect", response_model=ConnectorView)
    def oauth_disconnect(connector_id: str) -> ConnectorView:
        if registry.get_connector(connector_id) is None:
            raise HTTPException(404, f"no connector '{connector_id}'")
        tokens.remove(connector_id)
        return _connector_view(connector_id)

    @app.get("/api/errors", response_model=list[LoadErrorView])
    def list_errors() -> list[LoadErrorView]:
        # Surfaced on the board so a tile/connector that failed to load says why.
        return [
            LoadErrorView(kind=e.kind, source=e.source, errors=e.errors) for e in registry.errors
        ]

    @app.post("/api/reload")
    def reload_board() -> dict:
        # Re-scan connectors/ and tiles/ from disk (after editing files).
        registry.rescan(root)
        return {
            "connectors": len(registry.connectors),
            "tiles": len(registry.tiles),
            "errors": len(registry.errors),
        }

    @app.post("/api/tiles", response_model=TileSummary, status_code=201)
    def create_tile(body: CreateTileRequest) -> TileSummary:
        tile_id = body.id or slugify(body.name)
        fields = dict(
            id=tile_id,
            name=body.name,
            icon=body.icon,
            description=body.description,
            instructions=body.instructions,
            permission_tier=body.permission_tier,
            connector=body.connector,
            allowed_tools=body.allowed_tools,
            wants_input=body.wants_input,
            input_hint=body.input_hint,
            schedule=body.schedule,
        )
        try:
            manifest_dict = build_manifest(**fields)  # schema validation
            if body.connector:
                lc = registry.get_connector(body.connector)
                if lc is None:
                    raise ScaffoldError(f"no connector '{body.connector}'")
                errors = validate_tile_against_connector(
                    TileManifest.model_validate(manifest_dict), lc.manifest
                )
                if errors:
                    raise ScaffoldError("; ".join(errors))
            scaffold_tile(root, **fields)
        except ScaffoldError as exc:
            raise HTTPException(400, str(exc)) from exc

        registry.rescan(root)  # the new tile now shows on the board
        return _tile_summary(tile_id)

    @app.put("/api/tiles/{tile_id}", response_model=TileSummary)
    def edit_tile(tile_id: str, body: UpdateTileRequest) -> TileSummary:
        loaded = registry.get_tile(tile_id)
        if loaded is None:
            raise HTTPException(404, f"no tile '{tile_id}'")
        cm = None
        if loaded.manifest.connector:
            lc = registry.get_connector(loaded.manifest.connector)
            cm = lc.manifest if lc else None
        try:
            update_tile(root, tile_id, body.model_dump(), cm)
        except ScaffoldError as exc:
            raise HTTPException(400, str(exc)) from exc
        registry.rescan(root)
        return _tile_summary(tile_id)

    @app.get("/api/schedules", response_model=list[ScheduledTileView])
    def list_schedules() -> list[ScheduledTileView]:
        out = []
        for tid in sorted(registry.tiles):
            sched = registry.tiles[tid].manifest.schedule
            if sched is not None:
                out.append(
                    ScheduledTileView(
                        tile_id=tid, every=sched.every, interval_seconds=sched.interval_seconds()
                    )
                )
        return out

    @app.get("/api/tiles/{tile_id}/flow", response_model=FlowCandidatesView)
    def tile_flow(tile_id: str) -> FlowCandidatesView:
        if registry.get_tile(tile_id) is None:
            raise HTTPException(404, f"no tile '{tile_id}'")
        return FlowCandidatesView(**runtime.flow_candidates(tile_id))

    @app.post("/api/flows/run", response_model=FlowRunResponse)
    async def run_flow(body: FlowRunRequest) -> FlowRunResponse:
        try:
            outcomes = await runtime.run_flow(body.tiles, body.input)
        except RuntimeError_ as exc:
            raise HTTPException(404, str(exc)) from exc
        except BrainResolutionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ModelClientError as exc:
            raise HTTPException(502, f"model call failed: {exc}") from exc
        return FlowRunResponse(
            steps=[
                FlowStepView(
                    tile_id=o.tile_id,
                    result=o.result,
                    queued=len(o.gate.queued),
                    executed=len(o.gate.executed),
                    rejected=len(o.gate.rejected),
                )
                for o in outcomes
            ]
        )

    @app.delete("/api/tiles/{tile_id}")
    def remove_tile(tile_id: str) -> dict:
        if registry.get_tile(tile_id) is None:
            raise HTTPException(404, f"no tile '{tile_id}'")
        delete_tile(root, tile_id)
        registry.rescan(root)
        return {"deleted": tile_id}

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
        except BrainResolutionError as exc:
            raise HTTPException(409, str(exc)) from exc  # no brain configured
        except ModelClientError as exc:
            # Upstream model failure (rate limit, overload, auth, network) after
            # retries — a clean 502 the board can show, not a 500 traceback.
            raise HTTPException(502, f"model call failed: {exc}") from exc
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

    def _persist_brain() -> None:
        # Save to brain.local.yaml so UI changes survive a restart. The offline
        # echo store has no path; there's nothing (and no key) to persist there.
        if store.path is not None:
            store.save()

    @app.post("/api/providers", response_model=list[ProviderView])
    def add_provider(body: AddProviderRequest) -> list[ProviderView]:
        store.add_provider(body.provider, make_default=body.make_default)
        _persist_brain()
        return [_provider_view(p) for p in store.config.providers]

    @app.put("/api/brain/default", response_model=list[ProviderView])
    def set_default(body: SetDefaultRequest) -> list[ProviderView]:
        if store.config.get(body.provider_id) is None:
            raise HTTPException(404, f"no provider '{body.provider_id}'")
        store.set_default(body.provider_id)
        _persist_brain()
        return [_provider_view(p) for p in store.config.providers]

    @app.delete("/api/providers/{provider_id}", response_model=list[ProviderView])
    def remove_provider(provider_id: str) -> list[ProviderView]:
        if store.config.get(provider_id) is None:
            raise HTTPException(404, f"no provider '{provider_id}'")
        store.remove_provider(provider_id)
        _persist_brain()
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
