"""Scenario runner skeleton for BAYMAX evals."""

from __future__ import annotations

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


def run_scenario(scenario: Scenario, response: AgentResponse) -> ScenarioRunResult:
    """Run one scenario using a prepared agent response."""

    execution = execute_tool_calls(
        initial_state=scenario.initial_state,
        tool_calls=response.tool_calls,
    )
    score = score_response(scenario, response)

    return ScenarioRunResult(
        scenario_id=scenario.id,
        score=score,
        tool_results=execution.tool_results,
        final_state=execution.final_state,
    )


def run_scenarios(scenarios: list[Scenario], agent: ScriptedAgent) -> list[ScenarioRunResult]:
    """Run scenarios through a scripted agent."""

    return [run_scenario(scenario, agent.invoke(scenario)) for scenario in scenarios]
