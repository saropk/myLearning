"""The daemon: FastAPI app, lifespan wiring, localhost binding.

One consciousness (core principle 4): this process owns state, and every client — the
Aegis UI now, the voice pipeline in phase 2 — is a thin client of this API. Killing a
client never affects Athena.

Security posture enforced here:
  * bind 127.0.0.1 only, plus a Host-header check so a rebound DNS name can't reach us;
  * a random per-install bearer token on every /api/* request;
  * no networking imports (the local brain is reached via athena.llm, see its docstring).
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .brain import Brain
from .config import Config, load_config
from .events import EventBus
from .llm import LLMUnavailable, OllamaClient
from .memory.store import Store
from .state import AthenaState, Modality, State
from .status import ErrorLog, build_report

UI_DIR = Path(__file__).resolve().parent / "ui"
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})
IDLE_TICK_S = 1.0


# --- request/response models ------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mode_hint: str | None = None


class StateRequest(BaseModel):
    state: State | None = None
    modality: Modality | None = None


class ValveRequest(BaseModel):
    level: int = Field(ge=0, le=3)


# --- auth -------------------------------------------------------------------------


def _request_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    # EventSource cannot set headers, so the SSE stream (and the first page load) may
    # carry the token as a query parameter. Same secret, same check.
    return request.query_params.get("token")


async def require_token(request: Request) -> None:
    expected: str = request.app.state.token
    supplied = _request_token(request)
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


Auth = Annotated[None, Depends(require_token)]


# --- app ---------------------------------------------------------------------------


def create_app(
    config: Config | None = None,
    *,
    store: Store | None = None,
    llm: OllamaClient | None = None,
) -> FastAPI:
    """Build the app. Dependencies are injectable so tests never need a real Ollama."""
    cfg = config or load_config()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.config = cfg
        app.state.store = store or Store(cfg.memory.db_path)
        app.state.token = app.state.store.ensure_token()
        app.state.llm = llm or OllamaClient(
            base_url=cfg.brain.ollama_host,
            timeout_s=cfg.brain.request_timeout_s,
            keep_alive=cfg.brain.keep_alive,
        )
        app.state.bus = EventBus()
        app.state.errors = ErrorLog()
        app.state.athena = AthenaState(
            cfg.state, valve_level=app.state.store.valve_level(cfg.valve.default_level)
        )
        app.state.brain = Brain(cfg.brain, app.state.llm)
        app.state.started_at = time.time()
        app.state.chat_lock = asyncio.Lock()

        last_end = app.state.store.get("last_session_end")
        if last_end:
            with contextlib.suppress(ValueError):
                app.state.athena.last_session_end = float(last_end)

        idle_task = asyncio.create_task(_idle_watchdog(app))
        try:
            yield
        finally:
            idle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await idle_task
            if llm is None:
                await app.state.llm.aclose()
            if store is None:
                app.state.store.close()

    app = FastAPI(title="Athena", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def loopback_only(request: Request, call_next: Any) -> Any:
        """Reject anything not addressed to this machine by its loopback name.

        Binding to 127.0.0.1 stops remote connections; this stops a malicious web page
        from using a DNS name that resolves to 127.0.0.1 to talk to the daemon.
        """
        host = (request.headers.get("host") or "").rsplit(":", 1)[0]
        if host and host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "invalid host"}, status_code=400)
        return await call_next(request)

    _register_routes(app)
    return app


def _broadcast_state(app: FastAPI) -> None:
    app.state.bus.publish("state", app.state.athena.snapshot())


def _persist_transition(app: FastAPI) -> None:
    st: AthenaState = app.state.athena
    if st.state is State.DORMANT and st.last_session_end is not None:
        app.state.store.set("last_session_end", str(st.last_session_end))


async def _idle_watchdog(app: FastAPI) -> None:
    """ACTIVE → DORMANT after the configured idle timeout, with a spoken confirmation.

    Phase 1 has no mouth yet, so the confirmation goes out as a `notice` event; phase 2's
    speak.py subscribes to the same event.
    """
    while True:
        await asyncio.sleep(IDLE_TICK_S)
        st: AthenaState = app.state.athena
        transition = st.check_idle()
        if transition is None:
            continue
        _persist_transition(app)
        app.state.bus.publish("notice", {"text": "Going quiet — you've been silent a while."})
        _broadcast_state(app)


def _register_routes(app: FastAPI) -> None:
    # --- UI shell -----------------------------------------------------------------
    # The shell and its assets are the same bytes on every install and carry no user
    # data; the token gates every /api/* route, which is where data lives. The page picks
    # the token up from the launch URL's ?token= and keeps it in sessionStorage.
    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.get("/ui/{filename}")
    async def ui_asset(filename: str) -> FileResponse:
        path = (UI_DIR / filename).resolve()
        if path.parent != UI_DIR or not path.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(path)

    # --- chat ---------------------------------------------------------------------
    @app.post("/api/chat")
    async def chat(request: Request, body: ChatRequest, _: Auth) -> dict[str, Any]:
        st: AthenaState = request.app.state.athena
        brain: Brain = request.app.state.brain
        before = st.state

        # One brain at a time: concurrent turns would interleave session context.
        async with request.app.state.chat_lock:
            reply = await brain.handle(body.message, st, mode_hint=body.mode_hint)

        if reply.error:
            request.app.state.errors.record("chat", reply.error)
        if st.state is not before:
            _persist_transition(request.app)
        _broadcast_state(request.app)

        return {
            "reply": reply.text,
            "route": reply.route,
            "source": reply.source,
            "control": reply.control,
            "error": reply.error,
            **st.snapshot(),
        }

    # --- events -------------------------------------------------------------------
    @app.get("/api/events")
    async def events(request: Request, _: Auth) -> StreamingResponse:
        bus: EventBus = request.app.state.bus
        snapshot = request.app.state.athena.snapshot()
        return StreamingResponse(
            bus.stream(snapshot),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    # --- state --------------------------------------------------------------------
    @app.get("/api/state")
    async def get_state(request: Request, _: Auth) -> dict[str, Any]:
        st: AthenaState = request.app.state.athena
        return {
            **st.snapshot(),
            "idle_timeout_s": st.config.idle_timeout_s,
            "follow_up_window_s": st.config.follow_up_window_s,
            "last_session_end": st.last_session_end,
        }

    @app.post("/api/state")
    async def set_state(request: Request, body: StateRequest, _: Auth) -> dict[str, Any]:
        """UI buttons mirror the voice phrases — same code path, no privileged shortcut."""
        st: AthenaState = request.app.state.athena
        if body.state is not None:
            st.apply_state(body.state, phrase="<api>")
            _persist_transition(request.app)
        if body.modality is not None:
            st.set_modality(body.modality)
        _broadcast_state(request.app)
        return st.snapshot()

    # --- valve --------------------------------------------------------------------
    @app.get("/api/valve")
    async def get_valve(request: Request, _: Auth) -> dict[str, Any]:
        st: AthenaState = request.app.state.athena
        return {
            "level": st.valve_level,
            "enforced": False,
            "note": (
                "Phase 1 stores the level and reports it; gateway/ does not exist yet, so "
                "no module in this build can make an outbound request at any level."
            ),
        }

    @app.post("/api/valve")
    async def set_valve(request: Request, body: ValveRequest, _: Auth) -> dict[str, Any]:
        st: AthenaState = request.app.state.athena
        request.app.state.store.set_valve_level(body.level)
        st.valve_level = body.level
        _broadcast_state(request.app)
        return {"level": st.valve_level, "enforced": False}

    # --- status -------------------------------------------------------------------
    @app.get("/api/status")
    async def status(request: Request, _: Auth) -> dict[str, Any]:
        cfg: Config = request.app.state.config
        st: AthenaState = request.app.state.athena
        resident: list[dict[str, Any]] = []
        brain_reachable = True
        try:
            resident = await request.app.state.llm.resident_models()
        except LLMUnavailable as exc:
            brain_reachable = False
            request.app.state.errors.record("status", str(exc))

        report = build_report(resident, st.state.value)
        return {
            "uptime_s": round(time.time() - request.app.state.started_at, 1),
            "state": st.state.value,
            "modality": st.modality.value,
            "valve": st.valve_level,
            "phase": 1,
            "brain": {
                "reachable": brain_reachable,
                "model": cfg.brain.active_model,
                "lite": cfg.brain.lite,
                "host": cfg.brain.ollama_host,
                "keep_alive": cfg.brain.keep_alive,
            },
            "models_loaded": resident,
            "ram": {
                "daemon_gb": report.daemon_gb,
                "models_gb": report.models_gb,
                "total_gb": report.total_gb,
                "budget_gb": report.budget_gb,
                "within_budget": report.within_budget,
                "machine_total_gb": report.machine_total_gb,
                "machine_available_gb": report.machine_available_gb,
                "detail": report.detail,
            },
            "config_source": str(cfg.source_path) if cfg.source_path else None,
            "db_path": str(cfg.memory.db_path),
            "event_subscribers": request.app.state.bus.subscriber_count,
            "last_errors": request.app.state.errors.recent(),
        }
