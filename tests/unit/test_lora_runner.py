from __future__ import annotations

import json
from pathlib import Path

from baymax.eval.lora_runner import (
    LocalLoraConfig,
    LocalLoraInvocation,
    build_lora_scenario_messages,
    parse_lora_agent_response,
    run_lora_scenario,
)
from baymax.eval.scenario_loader import load_scenario
from baymax.eval.scorer import AgentResponse, AgentToolCall

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def test_local_lora_config_allows_base_model_without_adapter() -> None:
    config = LocalLoraConfig()

    assert config.base_model == "Qwen/Qwen2.5-1.5B-Instruct"
    assert config.adapter_path is None


def test_parse_lora_agent_response_reads_xlam_tool_call() -> None:
    response = parse_lora_agent_response(
        json.dumps(
            [
                {
                    "name": "calendar.create_event",
                    "arguments": {
                        "title": "Linear algebra revision",
                        "start_date": "2026-05-19",
                        "start_time": "16:00",
                        "duration_minutes": 120,
                    },
                }
            ]
        )
    )

    assert [call.tool for call in response.tool_calls] == ["calendar.create_event"]
    assert response.tool_calls[0].arguments["duration_minutes"] == 120
    assert response.message is None


def test_parse_lora_agent_response_reads_openai_style_function_call() -> None:
    response = parse_lora_agent_response(
        json.dumps(
            [
                {
                    "function": {
                        "name": "notion.create_task",
                        "arguments": '{"title":"Physics lab report"}',
                    }
                }
            ]
        )
    )

    assert [call.tool for call in response.tool_calls] == ["notion.create_task"]
    assert response.tool_calls[0].arguments == {"title": "Physics lab report"}


def test_parse_lora_agent_response_reads_alternating_tool_argument_list() -> None:
    response = parse_lora_agent_response(
        json.dumps(
            [
                "calendar.create_event",
                {
                    "title": "Chemistry Review",
                    "start_date": "2026-05-18",
                    "start_time": "20:00",
                    "duration_minutes": 60,
                },
            ]
        )
    )

    assert [call.tool for call in response.tool_calls] == ["calendar.create_event"]
    assert response.tool_calls[0].arguments["title"] == "Chemistry Review"


def test_parse_lora_agent_response_reads_params_arguments() -> None:
    response = parse_lora_agent_response(
        json.dumps(
            [
                {
                    "tool": "request_clarification",
                    "params": {"question": "Do you want me to cancel it?"},
                }
            ]
        )
    )

    assert response.tool_calls == []
    assert response.message == "Do you want me to cancel it?"


def test_parse_lora_agent_response_converts_meta_clarification_to_message() -> None:
    response = parse_lora_agent_response(
        json.dumps(
            [
                {
                    "name": "request_clarification",
                    "arguments": {"question": "Who should I email?"},
                }
            ]
        )
    )

    assert response.tool_calls == []
    assert response.message == "Who should I email?"


def test_parse_lora_agent_response_preserves_unparseable_text_as_message() -> None:
    response = parse_lora_agent_response("I need the recipient.")

    assert response.tool_calls == []
    assert response.message == "I need the recipient."


def test_build_lora_scenario_messages_includes_eval_context_and_tools() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")

    messages = build_lora_scenario_messages(scenario)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "calendar.create_event" in messages[1]["content"]
    assert "request_clarification" in messages[1]["content"]
    assert "2026-05-18T09:00:00+00:00" in messages[1]["content"]
    assert "Schedule linear algebra revision" in messages[1]["content"]


def test_run_lora_scenario_scores_parsed_response() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_create_001.json")
    agent = _FakeLoraAgent(
        LocalLoraInvocation(
            raw_text="raw json",
            response=AgentResponse(
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
            ),
        )
    )

    result = run_lora_scenario(scenario, agent, run_id="run_test")

    assert result.scenario_id == "calendar_create_001"
    assert result.task_id == "run_test.calendar_create_001.0"
    assert result.raw_model_output == "raw json"
    assert result.agent_response is not None
    assert result.score.task_success is True
    assert result.final_state["calendar_events"][0]["title"] == "Linear algebra revision"


class _FakeLoraAgent:
    def __init__(self, invocation: LocalLoraInvocation) -> None:
        self._invocation = invocation

    def invoke(self, scenario: object) -> LocalLoraInvocation:
        del scenario
        return self._invocation
