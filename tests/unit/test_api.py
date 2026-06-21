"""Tests for the FastAPI service.

These tests construct a fresh app and override the inference backend with a
fake so no OpenAI calls happen. Pure plumbing tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from baymax.core.contracts import ToolCallStep
from baymax.service.api import AppState, InvokeRequest  # noqa: F401
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
)
from baymax.telemetry.logger import TelemetryLogger

fake_modules_available = True
try:
    import baymax.tools.fake_base  # noqa: F401
except ImportError:
    fake_modules_available = False

pytestmark = pytest.mark.skipif(
    not fake_modules_available,
    reason="Ronin's fake adapter modules not yet available (PR #3 not merged).",
)


@dataclass
class _FakeBackend(InferenceBackend):
    plan_response: PlanResult
    interpret_response: InterpretResult = InterpretResult(response_text="ok done")

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        return self.plan_response

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        return self.interpret_response


def _build_test_app(plan_response: PlanResult) -> FastAPI:
    """Construct an app with a fake backend pre-installed (bypassing lifespan)."""
    import io

    # We construct the app WITHOUT lifespan so we can inject app state directly.
    app = FastAPI()

    state = AppState(
        inference=_FakeBackend(plan_response=plan_response),
        telemetry=TelemetryLogger(output_stream=io.StringIO()),
    )
    app.state.baymax = state

    # Re-register the endpoints against this app
    from baymax.service.api import health, invoke

    app.get("/health")(health)
    app.post("/invoke")(invoke)
    return app


def test_health_endpoint_returns_ok():
    app = _build_test_app(
        plan_response=PlanResult(
            plan=[],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["backend"] == "_FakeBackend"


def test_invoke_clarification_emits_empty_tool_calls():
    app = _build_test_app(
        plan_response=PlanResult(
            plan=None,
            intent_unclear=True,
            request_type=None,
            request_complexity=None,
            clarification_question="Which Sarah?",
            refusal_reason=None,
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/invoke",
            json={
                "user_input": "email sarah",
                "available_tools": ["gmail.send_email"],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tool_calls"] == []
        assert body["message"] == "Which Sarah?"


def test_invoke_happy_path_clipboard_read_write():
    app = _build_test_app(
        plan_response=PlanResult(
            plan=[
                ToolCallStep(tool="clipboard.write", arguments={"text": "hi"}),
            ],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/invoke",
            json={
                "user_input": "save 'hi' to clipboard",
                "available_tools": ["clipboard.write"],
                "initial_state": {},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["tool_calls"]) == 1
        assert body["tool_calls"][0]["tool"] == "clipboard.write"
        assert body["message"] == "ok done"


def test_invoke_rejects_invalid_initial_state():
    app = _build_test_app(
        plan_response=PlanResult(
            plan=[],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    with TestClient(app) as client:
        # clipboard expects {"text": str}; passing a list breaks pydantic
        response = client.post(
            "/invoke",
            json={
                "user_input": "x",
                "available_tools": ["clipboard.read"],
                "initial_state": {"clipboard": "not_a_dict"},
            },
        )
        assert response.status_code == 400
        assert "invalid initial_state" in response.json()["detail"].lower()


def test_invoke_validates_request_body():
    app = _build_test_app(
        plan_response=PlanResult(
            plan=[],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    with TestClient(app) as client:
        # Missing user_input
        response = client.post(
            "/invoke",
            json={"available_tools": ["clipboard.read"]},
        )
        assert response.status_code == 422  # FastAPI/pydantic validation error
