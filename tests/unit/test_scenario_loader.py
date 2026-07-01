from json import JSONDecodeError
from pathlib import Path

import pytest
from pydantic import ValidationError

from baymax.eval.scenario_loader import (
    ClarificationExpectedBehavior,
    RefusalExpectedBehavior,
    Scenario,
    ScenarioLoadError,
    ToolCallExpectedBehavior,
    ToolCallsExpectedBehavior,
    load_scenario,
    load_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def test_loads_all_v1_scenarios() -> None:
    scenarios = load_scenarios(SCENARIO_DIR)

    assert {scenario.id for scenario in scenarios} == {
        "calendar_ambiguous_tonight_001",
        "calendar_cancel_confirm_001",
        "calendar_clarify_time_001",
        "calendar_conflict_001",
        "calendar_contextual_reschedule_001",
        "calendar_create_001",
        "calendar_invalid_duration_001",
        "calendar_list_tomorrow_001",
        "calendar_multiple_matching_meetings_001",
        "calendar_no_matching_reschedule_001",
        "calendar_relative_time_001",
        "calendar_timezone_create_001",
        "calendar_update_duration_001",
        "clipboard_clarify_multiple_tasks_001",
        "clipboard_explicit_write_001",
        "clipboard_implicit_task_001",
        "clipboard_read_only_001",
        "clipboard_refusal_password_001",
        "clipboard_replace_contextual_001",
        "clipboard_task_from_copy_001",
        "clipboard_write_empty_001",
        "gmail_clarify_recipient_001",
        "gmail_contextual_thread_reply_001",
        "gmail_create_draft_001",
        "gmail_contextual_reply_001",
        "gmail_draft_vs_send_001",
        "gmail_implicit_draft_001",
        "gmail_invalid_recipient_001",
        "gmail_refusal_001",
        "gmail_search_sender_001",
        "gmail_send_confirmation_001",
        "gmail_send_email_001",
        "multi_tool_calendar_email_001",
        "multi_tool_calendar_notion_001",
        "multi_tool_clarify_missing_email_001",
        "multi_tool_clipboard_email_001",
        "multi_tool_task_email_001",
        "notion_clarify_multiple_tasks_001",
        "notion_contextual_complete_001",
        "notion_create_task_001",
        "notion_delete_confirm_001",
        "notion_duplicate_prevention_001",
        "notion_explicit_create_001",
        "notion_invalid_due_date_001",
        "notion_list_due_tomorrow_001",
        "notion_mark_done_no_match_001",
        "notion_multi_create_two_tasks_001",
        "notion_update_due_date_001",
        "scope_refusal_food_order_001",
        "tool_unavailable_email_001",
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


def test_loads_refusal_scenario_without_tool_arguments() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_refusal_001.json")

    assert scenario.difficulty == "explicit"
    assert isinstance(scenario.expected_behavior, RefusalExpectedBehavior)
    assert scenario.expected_behavior.reason_contains == ["impersonate", "professor"]


def test_loads_multi_step_scenario_with_ordered_tool_calls() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")

    assert scenario.difficulty == "multi_step"
    assert isinstance(scenario.expected_behavior, ToolCallsExpectedBehavior)
    assert [call.tool for call in scenario.expected_behavior.calls] == [
        "notion.create_task",
        "gmail.create_draft",
    ]
    assert scenario.expected_behavior.calls[1].arguments["recipient"] == "marv@example.com"


def test_rejects_multi_step_behavior_with_one_tool_call() -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    scenario_data = valid_scenario.model_dump(mode="json")
    scenario_data["expected_behavior"]["calls"] = scenario_data["expected_behavior"]["calls"][:1]

    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario_data)


def test_rejects_duplicate_success_criteria() -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "notion_create_task_001.json")
    scenario_data = valid_scenario.model_dump(mode="json")
    scenario_data["success_criteria"] = ["correct_title", "correct_title"]

    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario_data)


def test_rejects_invalid_id_pattern() -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")
    scenario_data = valid_scenario.model_dump(mode="json")
    scenario_data["id"] = "CalendarCreate1"

    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario_data)


def test_empty_directory_returns_empty_list(tmp_path: Path) -> None:
    assert load_scenarios(tmp_path) == []


def test_malformed_json_raises_json_decode_error(tmp_path: Path) -> None:
    malformed_scenario = tmp_path / "broken.json"
    malformed_scenario.write_text('{"id": "broken_001",', encoding="utf-8")

    with pytest.raises(JSONDecodeError):
        load_scenario(malformed_scenario)


def test_load_scenarios_reports_file_path_for_malformed_json(tmp_path: Path) -> None:
    malformed_scenario = tmp_path / "broken.json"
    malformed_scenario.write_text('{"id": "broken_001",', encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match="broken.json") as error_info:
        load_scenarios(tmp_path)

    assert error_info.value.failures[0].path == malformed_scenario
    assert isinstance(error_info.value.failures[0].error, JSONDecodeError)


def test_load_scenarios_reports_file_path_for_validation_error(tmp_path: Path) -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")
    scenario_data = valid_scenario.model_dump_json()
    invalid_scenario = tmp_path / "invalid_id.json"
    invalid_scenario.write_text(
        scenario_data.replace("calendar_create_001", "CalendarCreate1"),
        encoding="utf-8",
    )

    with pytest.raises(ScenarioLoadError, match="invalid_id.json") as error_info:
        load_scenarios(tmp_path)

    assert error_info.value.failures[0].path == invalid_scenario
    assert isinstance(error_info.value.failures[0].error, ValidationError)


def test_load_scenarios_reports_all_failed_files(tmp_path: Path) -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")
    invalid_scenario_data = valid_scenario.model_dump_json().replace(
        "calendar_create_001",
        "CalendarCreate1",
    )
    invalid_scenario = tmp_path / "invalid_id.json"
    invalid_scenario.write_text(invalid_scenario_data, encoding="utf-8")
    malformed_scenario = tmp_path / "broken.json"
    malformed_scenario.write_text('{"id": "broken_001",', encoding="utf-8")

    with pytest.raises(ScenarioLoadError) as error_info:
        load_scenarios(tmp_path)

    failed_paths = {failure.path.name for failure in error_info.value.failures}
    assert failed_paths == {"broken.json", "invalid_id.json"}
    assert "broken.json" in str(error_info.value)
    assert "invalid_id.json" in str(error_info.value)


def test_missing_file_path_raises_file_not_found_error(tmp_path: Path) -> None:
    missing_scenario = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        load_scenario(missing_scenario)


def test_rejects_current_time_without_timezone() -> None:
    valid_scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")
    scenario_data = valid_scenario.model_dump(mode="json")
    scenario_data["current_time"] = "2026-05-18T09:00:00"

    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario_data)
