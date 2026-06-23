"""FastAPI service exposing the agent over HTTP.

Per ADR 0005 (inference backend) and ADR 0001 (agent loop).

v1 endpoints:
    POST /invoke     — run one user request end-to-end, return AgentResponse JSON
    GET  /health     — liveness probe

Run locally with:
    uv run uvicorn baymax.service.api:app --reload --port 8000

For unit testing the API, use fastapi.testclient.TestClient + a fake
InferenceBackend (no OpenAI calls needed).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from baymax.core.agent import Agent
from baymax.core.contracts import AgentResponse
from baymax.core.dispatcher import FakeAdapterDispatcher
from baymax.service.inference import InferenceBackend, OpenAIBackend
from baymax.telemetry.logger import TelemetryLogger

# ---------- request/response models ----------


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
    status: str
    backend: str


# ---------- application state ----------


# DECISION: hold the inference backend at the app level so we don't create a
# new OpenAI client per request. The dispatcher IS created per request because
# it owns per-request state (the fake adapters' in-memory data).
class AppState:
    inference: InferenceBackend
    telemetry: TelemetryLogger

    def __init__(self, inference: InferenceBackend, telemetry: TelemetryLogger) -> None:
        self.inference = inference
        self.telemetry = telemetry


# ---------- lifespan + app construction ----------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Construct app-level singletons at startup."""
    # DECISION: telemetry destination is configurable via env var. Default
    # `traces.jsonl` in the current directory.
    telemetry_path = os.environ.get("BAYMAX_TELEMETRY_PATH", "traces.jsonl")
    telemetry = TelemetryLogger.configure(output_path=telemetry_path)

    backend_name = os.environ.get("BAYMAX_INFERENCE_BACKEND", "openai")
    # DECISION: only OpenAI is wired in v1. Adding Anthropic/MLX is a v2 task.
    if backend_name == "openai":
        model = os.environ.get("BAYMAX_OPENAI_MODEL", "gpt-4o-mini")
        inference: InferenceBackend = OpenAIBackend(model=model)
    else:
        raise RuntimeError(
            f"unsupported BAYMAX_INFERENCE_BACKEND={backend_name!r}; "
            f"only 'openai' is supported in v1"
        )

    app.state.baymax = AppState(inference=inference, telemetry=telemetry)
    yield
    # No teardown needed for v1


def create_app() -> FastAPI:
    """Factory — construct a fresh app. Useful for testing."""
    return FastAPI(
        title="BAYMAX agent service",
        version="0.1.0",
        description="HTTP front-end for the BAYMAX personal-task agent.",
        lifespan=lifespan,
    )


# Module-level app for `uvicorn baymax.service.api:app`.
app = create_app()


# ---------- endpoints ----------


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Liveness probe + backend identity."""
    state: AppState = request.app.state.baymax
    return HealthResponse(
        status="ok",
        backend=type(state.inference).__name__,
    )


@app.post("/invoke", response_model=AgentResponse)
async def invoke(req: InvokeRequest, request: Request) -> AgentResponse:
    """Run one user request end-to-end. Returns the boundary AgentResponse."""
    state: AppState = request.app.state.baymax

    # DECISION: build a fresh dispatcher per request so each request gets its
    # own in-memory fake-adapter state. This matches eval scenarios where
    # each scenario provides its own initial_state.
    try:
        dispatcher = FakeAdapterDispatcher(initial_state=req.initial_state)
    except Exception as exc:
        # Bad initial_state (e.g., wrong shape for a fake adapter) — surface
        # as 400, not 500, since it's a client mistake.
        raise HTTPException(status_code=400, detail=f"invalid initial_state: {exc}") from exc

    agent = Agent(
        inference=state.inference,
        dispatcher=dispatcher,
        telemetry=state.telemetry,
    )

    response = await agent.handle_request(
        user_input=req.user_input,
        available_tools=req.available_tools,
        context=req.context,
        tool_schemas=req.tool_schemas,
        run_id=req.run_id,
    )
    return response
