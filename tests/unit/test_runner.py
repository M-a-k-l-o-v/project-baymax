from pathlib import Path

import pytest

from baymax.eval.runner import (
    MissingScriptedResponseError,
    ScriptedAgent,
    run_scenario,
    run_scenarios,
)
from baymax.eval.scenario_loader import load_scenario
from baymax.eval.scorer import AgentResponse, AgentToolCall

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def test_run_scenario_executes_and_scores_tool_call() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="calendar.create_event",
                arguments={
                    "title": "Linear algebra revision",
                    "start_date": "2026-05-19",
                    "start_time": "16:00",
                    "duration_minutes": 120,
                },
            )
        ]
    )

    result = run_scenario(scenario, response)

    assert result.scenario_id == "calendar_create_001"
    assert result.score.task_success is True
    assert result.tool_results[0].success is True
    assert result.final_state["calendar_events"][0]["title"] == "Linear algebra revision"


def test_run_scenario_scores_clarification_without_tool_execution() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_clarify_recipient_001.json")
    response = AgentResponse(message="Who is the recipient?")

    result = run_scenario(scenario, response)

    assert result.scenario_id == "gmail_clarify_recipient_001"
    assert result.score.task_success is True
    assert result.score.clarification_accuracy == 1.0
    assert result.tool_results == []
    assert result.final_state["gmail_drafts"] == []
    assert result.final_state["sent_emails"] == []


def test_run_scenario_executes_and_scores_multi_step_response() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="notion.create_task",
                arguments={"title": "Physics lab report"},
            ),
            AgentToolCall(
                tool="gmail.create_draft",
                arguments={
                    "recipient": "marv@example.com",
                    "body": "I added it to Notion.",
                },
            ),
        ]
    )

    result = run_scenario(scenario, response)

    assert result.scenario_id == "multi_tool_task_email_001"
    assert result.score.task_success is True
    assert [tool_result.tool for tool_result in result.tool_results] == [
        "notion.create_task",
        "gmail.create_draft",
    ]
    assert result.final_state["notion_tasks"][0]["title"] == "Physics lab report"
    assert result.final_state["gmail_drafts"][0]["recipient"] == "marv@example.com"


def test_run_scenarios_uses_scripted_agent_responses() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_clarify_time_001.json")
    agent = ScriptedAgent(
        responses={
            "calendar_clarify_time_001": AgentResponse(message="What time should I schedule it?")
        }
    )

    results = run_scenarios([scenario], agent)

    assert len(results) == 1
    assert results[0].scenario_id == "calendar_clarify_time_001"
    assert results[0].score.task_success is True


def test_scripted_agent_raises_clear_error_for_missing_response() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_clarify_time_001.json")
    agent = ScriptedAgent(responses={})

    with pytest.raises(
        MissingScriptedResponseError,
        match="missing scripted response for scenario: calendar_clarify_time_001",
    ):
        agent.invoke(scenario)
