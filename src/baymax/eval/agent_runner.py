"""Run BAYMAX agent implementations against eval scenarios."""

from __future__ import annotations

import json
from io import StringIO
from time import perf_counter
from typing import Any

from baymax.core.agent import Agent
from baymax.core.contracts import (
    AgentResponse as CoreAgentResponse,
)
from baymax.core.contracts import (
    ToolCallResult,
    ToolCallStep,
)
from baymax.eval.fake_executor import FakeToolExecutor
from baymax.eval.runner import ScenarioRunResult
from baymax.eval.scenario_loader import Scenario
from baymax.eval.scorer import AgentResponse, AgentToolCall, score_response
from baymax.service.inference import InferenceBackend
from baymax.telemetry.logger import TelemetryLogger
from baymax.tools.fake_base import FakeToolResult

FAKE_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "calendar.create_event": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "start_date": {"type": "string"},
            "start_time": {"type": "string"},
            "duration_minutes": {"type": "integer", "minimum": 1},
        },
        "required": ["title", "start_date", "start_time", "duration_minutes"],
    },
    "calendar.update_event": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "event_id": {"type": "string"},
            "title": {"type": "string"},
            "start_date": {"type": "string"},
            "start_time": {"type": "string"},
            "duration_minutes": {"type": "integer", "minimum": 1},
        },
        "required": ["event_id"],
    },
    "notion.create_task": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "due_date": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "done"]},
        },
        "required": ["title"],
    },
    "notion.update_task": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "task_id": {"type": "string"},
            "title": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "done"]},
            "due_date": {"type": "string"},
        },
        "required": ["task_id"],
    },
    "gmail.create_draft": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recipient": {"type": "string"},
            "body": {"type": "string"},
            "subject": {"type": "string"},
            "thread_id": {"type": "string"},
        },
        "required": ["recipient", "body"],
    },
    "gmail.send_email": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recipient": {"type": "string"},
            "body": {"type": "string"},
            "subject": {"type": "string"},
        },
        "required": ["recipient", "body"],
    },
    "clipboard.read": {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    },
    "clipboard.write": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    },
}


class ScenarioFakeDispatcher:
    """Async dispatcher that routes core agent tool steps to fake adapters."""

    def __init__(self, initial_state: dict[str, Any]) -> None:
        self._executor = FakeToolExecutor(initial_state)
        self.tool_results: list[FakeToolResult] = []

    async def dispatch(self, step: ToolCallStep) -> ToolCallResult:
        execution = self._executor.execute(
            [AgentToolCall(tool=step.tool, arguments=step.arguments)]
        )
        tool_result = execution.tool_results[0]
        self.tool_results.append(tool_result)
        return ToolCallResult(
            success=tool_result.success,
            tool=tool_result.tool,
            error=tool_result.error,
            data=tool_result.data,
        )

    def export_state(self) -> dict[str, Any]:
        return self._executor.export_state()


async def run_agent_scenario(
    *,
    scenario: Scenario,
    inference: InferenceBackend,
    run_id: str,
) -> ScenarioRunResult:
    """Run one scenario through Marv's agent core and score the boundary response."""

    dispatcher = ScenarioFakeDispatcher(scenario.initial_state)
    telemetry_stream = StringIO()
    telemetry = TelemetryLogger(output_stream=telemetry_stream)
    agent = Agent(
        inference=inference,
        dispatcher=dispatcher.dispatch,
        telemetry=telemetry,
    )

    started_at = perf_counter()
    core_response = await agent.handle_request(
        user_input=scenario.user_input,
        available_tools=scenario.available_tools,
        context={
            "current_time": scenario.current_time.isoformat(),
            "initial_state": scenario.initial_state,
        },
        tool_schemas={
            tool: FAKE_TOOL_SCHEMAS[tool]
            for tool in scenario.available_tools
            if tool in FAKE_TOOL_SCHEMAS
        },
        run_id=run_id,
    )
    latency_ms = int((perf_counter() - started_at) * 1000)

    response = _to_eval_agent_response(core_response)
    score = score_response(scenario, response)
    trace_summary = _extract_trace_summary(telemetry_stream.getvalue())

    return ScenarioRunResult(
        scenario_id=scenario.id,
        trace_id=trace_summary.get("trace_id"),
        task_id=f"{run_id}.{scenario.id}.0",
        latency_ms=latency_ms,
        cost_usd=float(trace_summary.get("cost_usd", 0.0)),
        agent_response=response,
        score=score,
        tool_results=dispatcher.tool_results,
        final_state=dispatcher.export_state(),
    )


async def run_agent_scenarios(
    *,
    scenarios: list[Scenario],
    inference: InferenceBackend,
    run_id: str,
) -> list[ScenarioRunResult]:
    """Run multiple scenarios through Marv's agent core."""

    results: list[ScenarioRunResult] = []
    for scenario in scenarios:
        results.append(
            await run_agent_scenario(
                scenario=scenario,
                inference=inference,
                run_id=run_id,
            )
        )
    return results


def _to_eval_agent_response(response: CoreAgentResponse) -> AgentResponse:
    return AgentResponse.model_validate(response.model_dump())


def _extract_trace_summary(jsonl: str) -> dict[str, Any]:
    for line in reversed([line for line in jsonl.splitlines() if line.strip()]):
        event = json.loads(line)
        if event.get("event") == "trace_summary":
            return event
    return {}
