"""FastAPI service exposing the agent over HTTP.

Per ADR 0001 (agent loop) + ADR 0011 (backend interface v2).

Endpoints:
    POST /invoke     — run one user request end-to-end. Returns AgentResponse
                       (200) or backend error body (500).
    GET  /health     — readiness probe. 503 while warmup runs; 200 once ready.

Run locally with:
    uv run uvicorn baymax.service.api:app --reload --port 8000

Environment (per ADR 0011 §B):
    BAYMAX_BACKEND        openai | mlx (default: openai)
    BAYMAX_MODEL_ID       model identifier registered in models/models.json
                          (default: gpt-4o-mini when backend=openai)
    BAYMAX_TELEMETRY_PATH trace file destination (default: traces.jsonl)
    OPENAI_API_KEY        required when backend=openai
    MLX_MODEL_PATH        required when backend=mlx (fallback if registry
                          entry omits adapter_path)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from baymax.core.agent import Agent
from baymax.core.contracts import AgentResponse
from baymax.core.dispatcher import FakeAdapterDispatcher
from baymax.core.exceptions import BackendConfigError, BackendError
from baymax.service.inference import InferenceBackend, OpenAIBackend
from baymax.telemetry.logger import TelemetryLogger

_logger = logging.getLogger("baymax.api")


# ---------------------------------------------------------------------------
# Backend factory (per ADR 0011 §B3 — factory dict pattern).
# ---------------------------------------------------------------------------


def _openai_backend_factory(model_id: str) -> InferenceBackend:
    return OpenAIBackend(model_id=model_id)


def _mlx_backend_factory(model_id: str) -> InferenceBackend:
    # Lazy import — MLXBackend imports mlx_lm which only installs on Apple Silicon.
    from baymax.service.mlx_backend import MLXBackend

    return MLXBackend(model_id=model_id)


BACKENDS: dict[str, Any] = {
    "openai": _openai_backend_factory,
    "mlx": _mlx_backend_factory,
}


# ---------------------------------------------------------------------------
# Request / response models.
# ---------------------------------------------------------------------------


class InvokeRequest(BaseModel):
    """Body of POST /invoke."""

    model_config = ConfigDict(extra="forbid")

    user_input: str = Field(min_length=1)
    available_tools: list[str] = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    tool_schemas: dict[str, dict[str, Any]] = Field(default_factory=dict)
    initial_state: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None


class HealthResponse(BaseModel):
    """Body of GET /health (per ADR 0011 §C2)."""

    model_config = ConfigDict(extra="forbid")

    ready: bool
    reason: str | None = None  # populated when ready=False
    backend: str | None = None  # populated when ready=True
    model_id: str | None = None  # populated when ready=True


# ---------------------------------------------------------------------------
# Application state.
# ---------------------------------------------------------------------------


class AppState:
    """App-level singletons held across requests."""

    inference: InferenceBackend
    telemetry: TelemetryLogger
    warmed_up: bool

    def __init__(self, inference: InferenceBackend, telemetry: TelemetryLogger) -> None:
        self.inference = inference
        self.telemetry = telemetry
        self.warmed_up = False


# ---------------------------------------------------------------------------
# Lifespan — construct backend, run warmup, gate /health.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Construct backend + warmup + hold singletons.

    Per ADR 0011 §B5 (lifespan-startup validation) and §C (warmup blocks
    /health). Any construction / warmup failure raises loudly and uvicorn
    exits before requests are accepted.
    """
    telemetry_path = os.environ.get("BAYMAX_TELEMETRY_PATH", "traces.jsonl")
    telemetry = TelemetryLogger.configure(output_path=telemetry_path)

    backend_name = os.environ.get("BAYMAX_BACKEND", "openai")
    if backend_name not in BACKENDS:
        raise BackendConfigError(
            backend=backend_name,
            missing=f"BAYMAX_BACKEND must be one of {sorted(BACKENDS)}",
            hint=f"Set BAYMAX_BACKEND to one of {sorted(BACKENDS)} in the environment.",
        )

    # Sensible default when backend=openai and BAYMAX_MODEL_ID unset.
    default_model = "gpt-4o-mini" if backend_name == "openai" else None
    model_id = os.environ.get("BAYMAX_MODEL_ID", default_model)
    if model_id is None:
        raise BackendConfigError(
            backend=backend_name,
            missing="BAYMAX_MODEL_ID",
            hint=(
                f"BAYMAX_MODEL_ID must be set when backend={backend_name!r}. "
                "It must resolve to an entry in models/models.json (see ADR 0012)."
            ),
        )

    inference = BACKENDS[backend_name](model_id)
    app.state.baymax = AppState(inference=inference, telemetry=telemetry)

    # Warmup — blocks lifespan yield per ADR 0011 §C. Fail loud on any error.
    _logger.info("backend_warmup_start", extra={"backend": backend_name, "model_id": model_id})
    await inference.warmup()
    app.state.baymax.warmed_up = True
    _logger.info(
        "backend_ready",
        extra={"backend": backend_name, "model_id": model_id},
    )

    yield
    # No teardown work needed in v1.


def create_app() -> FastAPI:
    """Factory — construct a fresh app. Useful for testing."""
    fastapi_app = FastAPI(
        title="BAYMAX agent service",
        version="0.2.0",
        description="HTTP front-end for the BAYMAX personal-task agent.",
        lifespan=lifespan,
    )
    _register_exception_handlers(fastapi_app)
    return fastapi_app


# ---------------------------------------------------------------------------
# Exception handlers.
# ---------------------------------------------------------------------------


def _register_exception_handlers(fastapi_app: FastAPI) -> None:
    """Wire up BackendError → HTTP 500 per ADR 0011 §E2 (Option A locked 2026-08-26)."""

    @fastapi_app.exception_handler(BackendError)
    async def _handle_backend_error(request: Request, exc: BackendError) -> JSONResponse:
        # Per ADR 0011 §E2: 500 body has structured fields, NO stack trace or
        # underlying repr (those live in the trace file per ADR 0010 redaction).
        body = {
            "error": "backend_error",
            "kind": exc.kind,
            "backend": exc.backend,
            "message": str(exc),
            "attempts": len(exc.attempts_history),
        }
        _logger.warning(
            "backend_error_response",
            extra={
                "event": "backend_error_response",
                "kind": exc.kind,
                "backend": exc.backend,
                "attempts": len(exc.attempts_history),
            },
        )
        return JSONResponse(status_code=500, content=body)


# Module-level app for `uvicorn baymax.service.api:app`.
app = create_app()


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    """Readiness probe. 503 while warmup runs (per ADR 0011 §C2); 200 once ready."""
    state: AppState | None = getattr(request.app.state, "baymax", None)
    if state is None or not state.warmed_up:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": "warming_up"},
        )
    return JSONResponse(
        status_code=200,
        content={
            "ready": True,
            "backend": state.inference.provider,
            "model_id": state.inference.model_id,
        },
    )


@app.post("/invoke", response_model=AgentResponse)
async def invoke(req: InvokeRequest, request: Request) -> AgentResponse:
    """Run one user request end-to-end.

    Returns AgentResponse on success (200). Backend failures propagate as
    BackendError and are converted to HTTP 500 by the exception handler
    per ADR 0011 §E2. Bad initial_state → 400.
    """
    state: AppState = request.app.state.baymax

    try:
        dispatcher = FakeAdapterDispatcher(initial_state=req.initial_state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid initial_state: {exc}") from exc

    agent = Agent(
        inference=state.inference,
        dispatcher=dispatcher,
        telemetry=state.telemetry,
    )

    # NOTE: agent code deliberately does NOT catch BackendError. It bubbles
    # up here and the registered exception handler produces the 500 response.
    return await agent.handle_request(
        user_input=req.user_input,
        available_tools=req.available_tools,
        context=req.context,
        tool_schemas=req.tool_schemas,
        run_id=req.run_id,
    )
