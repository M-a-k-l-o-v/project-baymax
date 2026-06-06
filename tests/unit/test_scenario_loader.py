from pathlib import Path

import pytest
from pydantic import ValidationError

from baymax.eval.scenario_loader import (
    ClarificationExpectedBehavior,
    Scenario,
    ToolCallExpectedBehavior,
    load_scenario,
    load_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def test_loads_all_v1_scenarios() -> None:
    scenarios = load_scenarios(SCENARIO_DIR)

    assert {scenario.id for scenario in scenarios} == {
        "calendar_create_001",
        "gmail_clarify_recipient_001",
        "notion_create_task_001",
    }


def test_loads_tool_call_scenario() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")

    assert scenario.difficulty == "implicit"
    assert isinstance(scenario.expected_behavior, ToolCallExpectedBehavior)
    assert scenario.expected_behavior.tool == "calendar.create_event"
    assert scenario.expected_behavior.arguments["start_date"] == "2026-05-19"


def test_loads_clarification_scenario_without_tool_arguments() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_clarify_recipient_001.json")

    assert scenario.difficulty == "ambiguous"
    assert isinstance(scenario.expected_behavior, ClarificationExpectedBehavior)
    assert scenario.expected_behavior.question_contains == ["who", "recipient"]


def test_rejects_duplicate_success_criteria() -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "notion_create_task_001.json")
    scenario_data = valid_scenario.model_dump(mode="json")
    scenario_data["success_criteria"] = ["correct_title", "correct_title"]

    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario_data)
