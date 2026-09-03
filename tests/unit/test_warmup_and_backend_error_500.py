"""Tests for /health warmup gate (ADR 0011 §C2) and BackendError → 500 (§E2)."""

from __future__ import annotations

import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from baymax.core.exceptions import BackendError, RetryAttempt
from baymax.service.api import AppState, _register_exception_handlers, health, invoke
from baymax.service.inference import InferenceBackend, PlanResult
from baymax.telemetry.logger import TelemetryLogger
from tests.fakes.backend import FakeBackend, make_plan_result

# ---------------------------------------------------------------------------
# App builder — like tests/unit/test_api.py but explicit about warmup state.
# ---------------------------------------------------------------------------


def _build_app_with(backend: InferenceBackend, warmed_up: bool = True) -> FastAPI:
    """FastAPI test app with backend + warmup state directly injected."""
    app = FastAPI()
    state = AppState(inference=backend, telemetry=TelemetryLogger(output_stream=io.StringIO()))
    state.warmed_up = warmed_up
    app.state.baymax = state
    app.get("/health")(health)
    app.post("/invoke")(invoke)
    _register_exception_handlers(app)
    return app


# ---------------------------------------------------------------------------
# /health warmup gate — 503 pre-warmup, 200 post (ADR 0011 §C2).
# ---------------------------------------------------------------------------


def test_health_returns_503_before_warmup() -> None:
    backend = FakeBackend(model_id="qwen-1.5b-baymax-v1")
    app = _build_app_with(backend, warmed_up=False)
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["ready"] is False
        assert body["reason"] == "warming_up"


def test_health_returns_200_with_backend_info_after_warmup() -> None:
    backend = FakeBackend(model_id="qwen-1.5b-baymax-v1")
    app = _build_app_with(backend, warmed_up=True)
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["backend"] == "fake"
        assert body["model_id"] == "qwen-1.5b-baymax-v1"


def test_health_returns_503_when_baymax_state_absent() -> None:
    """Defensive: if lifespan hasn't populated state, /health should return 503, not 500."""
    app = FastAPI()
    app.get("/health")(health)
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["ready"] is False


# ---------------------------------------------------------------------------
# BackendError → 500 (ADR 0011 §E2, Option A locked 2026-08-26).
# ---------------------------------------------------------------------------


def test_invoke_returns_500_when_backend_raises_backend_error() -> None:
    """A BackendError raised during agent processing becomes HTTP 500 + JSON body."""
    err = BackendError(
        kind="retry_exhausted",
        message="openai backend failed after 3 attempt(s): http_500",
        attempts_history=[
            RetryAttempt(attempt=1, delay_before_ms=1000, cause="http_500", underlying_repr="err"),
            RetryAttempt(attempt=2, delay_before_ms=2000, cause="http_500", underlying_repr="err"),
            RetryAttempt(attempt=3, delay_before_ms=4000, cause="http_500", underlying_repr="err"),
        ],
        backend="openai",
    )
    backend = FakeBackend(plan_side_effects=[err])
    app = _build_app_with(backend)

    with TestClient(app) as client:
        resp = client.post(
            "/invoke",
            json={
                "user_input": "book a meeting tomorrow at 10am",
                "available_tools": ["calendar.create_event"],
                "tool_schemas": {"calendar.create_event": {"type": "object"}},
                "initial_state": {"calendar_events": []},
            },
        )

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "backend_error"
    assert body["kind"] == "retry_exhausted"
    assert body["backend"] == "openai"
    assert body["attempts"] == 3
    # Message present but no stack trace / underlying repr per redaction (§E2).
    assert "openai backend failed" in body["message"]
    assert "Traceback" not in body["message"]


def test_invoke_500_body_omits_underlying_and_stack() -> None:
    """No forensic detail leaks into the client-facing body per ADR 0010 redaction."""
    err = BackendError(
        kind="non_retriable",
        message="mlx backend failed after 1 attempt(s): mlx_deterministic",
        underlying=RuntimeError("secret path /Users/private/leaked"),
        backend="mlx",
    )
    backend = FakeBackend(plan_side_effects=[err])
    app = _build_app_with(backend)

    with TestClient(app) as client:
        resp = client.post(
            "/invoke",
            json={
                "user_input": "test",
                "available_tools": ["calendar.create_event"],
                "tool_schemas": {"calendar.create_event": {"type": "object"}},
                "initial_state": {"calendar_events": []},
            },
        )

    assert resp.status_code == 500
    body_str = str(resp.json())
    assert "secret path" not in body_str
    assert "/Users/private" not in body_str


def test_invoke_200_agent_response_when_no_backend_error() -> None:
    """Happy path: successful backend + happy agent = 200 + AgentResponse shape."""
    plan = make_plan_result(intent_unclear=True, clarification_question="Which meeting?")
    backend = FakeBackend(plan_side_effects=[plan])
    app = _build_app_with(backend)

    with TestClient(app) as client:
        resp = client.post(
            "/invoke",
            json={
                "user_input": "cancel my meeting",
                "available_tools": ["calendar.create_event"],
                "tool_schemas": {"calendar.create_event": {"type": "object"}},
                "initial_state": {"calendar_events": []},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    # AgentResponse boundary: {tool_calls, message}
    assert "tool_calls" in body
    assert "message" in body


# Silence unused-import warning for typing-only imports.
_ = (PlanResult,)
