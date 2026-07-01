from pathlib import Path

import pytest

from baymax.core.contracts import ToolCallStep
from baymax.eval.agent_runner import (
    ScenarioFakeDispatcher,
    run_agent_scenario,
)
from baymax.eval.scenario_loader import load_scenario
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


class FakeInferenceBackend(InferenceBackend):
    async def plan_task(self, request: PlanRequest) -> PlanResult:
        return PlanResult(
            plan=[
                ToolCallStep(
                    tool="calendar.create_event",
                    arguments={
                        "title": "Linear algebra revision",
                        "start_date": "2026-05-19",
                        "start_time": "16:00",
                        "duration_minutes": 120,
                    },
                )
            ],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        return InterpretResult(
            response_text="Scheduled linear algebra revision.",
            input_tokens=7,
            output_tokens=3,
            cost_usd=0.002,
        )


@pytest.mark.asyncio
async def test_scenario_fake_dispatcher_executes_step_against_fake_tools() -> None:
    dispatcher = ScenarioFakeDispatcher({"calendar_events": []})

    result = await dispatcher.dispatch(
        ToolCallStep(
            tool="calendar.create_event",
            arguments={
                "title": "Linear algebra revision",
                "start_date": "2026-05-19",
                "start_time": "16:00",
                "duration_minutes": 120,
            },
        )
    )

    assert result.success is True
    assert dispatcher.tool_results[0].tool == "calendar.create_event"
    assert dispatcher.export_state()["calendar_events"][0]["title"] == ("Linear algebra revision")


@pytest.mark.asyncio
async def test_run_agent_scenario_scores_core_agent_response() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")

    result = await run_agent_scenario(
        scenario=scenario,
        inference=FakeInferenceBackend(),
        run_id="run_test",
    )

    assert result.scenario_id == "calendar_create_001"
    assert result.task_id == "run_test.calendar_create_001.0"
    assert result.trace_id is not None
    assert result.cost_usd == 0.003
    assert result.score.task_success is True
    assert result.final_state["calendar_events"][0]["title"] == ("Linear algebra revision")
