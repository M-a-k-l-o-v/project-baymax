"""Scenario runner skeleton for BAYMAX evals."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict

from baymax.eval.fake_executor import execute_tool_calls
from baymax.eval.scenario_loader import Scenario
from baymax.eval.scorer import AgentResponse, ScenarioScore, score_response
from baymax.tools.fake_base import FakeToolResult


class MissingScriptedResponseError(KeyError):
    """Raised when a scripted agent has no response for a scenario."""


class ScenarioRunResult(BaseModel):
    """Result of running one scenario through the eval harness."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    trace_id: str | None = None
    task_id: str | None = None
    latency_ms: int
    cost_usd: float = 0.0
    raw_model_output: str | None = None
    agent_response: AgentResponse | None = None
    score: ScenarioScore
    tool_results: list[FakeToolResult]
    final_state: dict[str, Any]


class ScriptedAgent:
    """Agent that returns pre-written responses by scenario ID."""

    def __init__(self, responses: dict[str, AgentResponse]) -> None:
        self._responses = responses

    def invoke(self, scenario: Scenario) -> AgentResponse:
        try:
            return self._responses[scenario.id]
        except KeyError as error:
            raise MissingScriptedResponseError(
                f"missing scripted response for scenario: {scenario.id}"
            ) from error


def run_scenario(
    scenario: Scenario,
    response: AgentResponse,
    *,
    run_id: str | None = None,
) -> ScenarioRunResult:
    """Run one scenario using a prepared agent response."""

    started_at = perf_counter()
    execution = execute_tool_calls(
        initial_state=scenario.initial_state,
        tool_calls=response.tool_calls,
    )
    score = score_response(scenario, response)
    latency_ms = int((perf_counter() - started_at) * 1000)

    return ScenarioRunResult(
        scenario_id=scenario.id,
        task_id=f"{run_id}.{scenario.id}.0" if run_id else None,
        latency_ms=latency_ms,
        agent_response=response,
        score=score,
        tool_results=execution.tool_results,
        final_state=execution.final_state,
    )


def run_scenarios(
    scenarios: list[Scenario],
    agent: ScriptedAgent,
    *,
    run_id: str | None = None,
) -> list[ScenarioRunResult]:
    """Run scenarios through a scripted agent."""

    return [run_scenario(scenario, agent.invoke(scenario), run_id=run_id) for scenario in scenarios]
