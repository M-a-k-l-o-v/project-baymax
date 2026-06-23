"""End-to-end integration tests against real OpenAI + Ronin's fake adapters.

Two test classes:

1. `TestPlumbingWithFakeBackend` — verifies the wiring (scenario loader →
   agent → dispatcher → fake adapters → response) WITHOUT hitting OpenAI.
   Runs in CI. Skip-gated only on Ronin's fake-adapter modules being available.

2. `TestRealOpenAI` — hits real OpenAI gpt-4o-mini. Costs ~$0.001 per
   scenario. Skip-gated on the `BAYMAX_RUN_OPENAI_TESTS=1` env var so it
   doesn't run in CI by default. Run locally with:

       BAYMAX_RUN_OPENAI_TESTS=1 uv run pytest tests/integration/test_end_to_end.py::TestRealOpenAI
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from baymax.core.contracts import ToolCallStep
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
)

fake_modules_available = True
try:
    import baymax.tools.fake_base  # noqa: F401
except ImportError:
    fake_modules_available = False


REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def _load_scenario(name: str) -> dict:
    path = SCENARIO_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------- Class 1: plumbing test with FakeBackend (always runs) ----------


@pytest.mark.skipif(
    not fake_modules_available,
    reason="Ronin's fake adapter modules not yet available (PR #3 not merged).",
)
class TestPlumbingWithFakeBackend:
    """Verifies scenario loader → agent → dispatcher → adapter → response wiring."""

    @pytest.mark.asyncio
    async def test_notion_create_task_end_to_end(self):
        from baymax.core.agent import Agent
        from baymax.core.dispatcher import FakeAdapterDispatcher

        scenario = _load_scenario("notion_create_task_001")

        @dataclass
        class CannedBackend(InferenceBackend):
            async def plan_task(self, request: PlanRequest) -> PlanResult:
                # Hard-coded plan as if a model had picked the right tool.
                return PlanResult(
                    plan=[
                        ToolCallStep(
                            tool="notion.create_task",
                            arguments={"title": "buy milk"},
                        )
                    ],
                    intent_unclear=False,
                    request_type=None,
                    request_complexity=None,
                    clarification_question=None,
                    refusal_reason=None,
                )

            async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
                return InterpretResult(response_text="Added 'buy milk' to your tasks.")

        dispatcher = FakeAdapterDispatcher(initial_state=scenario.get("initial_state", {}))
        agent = Agent(inference=CannedBackend(), dispatcher=dispatcher)

        response = await agent.handle_request(
            user_input=scenario["user_input"],
            available_tools=scenario["available_tools"],
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool == "notion.create_task"
        assert response.message is not None and "milk" in response.message.lower()

        # Verify state actually changed in the fake adapter
        final_state = dispatcher.export_state()
        assert len(final_state["notion_tasks"]) == 1


# ---------- Class 2: real OpenAI smoke test (opt-in) ----------


@pytest.mark.skipif(
    not fake_modules_available,
    reason="Ronin's fake adapter modules not yet available (PR #3 not merged).",
)
@pytest.mark.skipif(
    os.environ.get("BAYMAX_RUN_OPENAI_TESTS") != "1",
    reason=(
        "Set BAYMAX_RUN_OPENAI_TESTS=1 to run real OpenAI integration tests "
        "(costs ~$0.001 per test)."
    ),
)
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set in environment.",
)
class TestRealOpenAI:
    """Smoke test against real OpenAI gpt-4o-mini. Costs real money — gated."""

    @pytest.mark.asyncio
    async def test_notion_create_task_with_real_model(self):
        from baymax.core.agent import Agent
        from baymax.core.dispatcher import FakeAdapterDispatcher
        from baymax.service.inference import OpenAIBackend

        scenario = _load_scenario("notion_create_task_001")

        dispatcher = FakeAdapterDispatcher(initial_state=scenario.get("initial_state", {}))
        agent = Agent(inference=OpenAIBackend(), dispatcher=dispatcher)

        response = await agent.handle_request(
            user_input=scenario["user_input"],
            available_tools=scenario["available_tools"],
        )

        # Real model — assertions are deliberately loose. The plumbing test
        # asserts strict shape; this just verifies "it didn't crash."
        assert response is not None
        assert response.message is not None or response.tool_calls
