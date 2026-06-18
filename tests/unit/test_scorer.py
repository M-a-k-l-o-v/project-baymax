from pathlib import Path

from baymax.eval.scenario_loader import load_scenario
from baymax.eval.scorer import AgentResponse, AgentToolCall, score_response

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def test_scores_correct_multi_step_tool_sequence_as_success() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="notion.create_task",
                arguments={"title": "Finish physics lab report"},
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

    score = score_response(scenario, response)

    assert score.task_success is True
    assert score.tool_call_accuracy == 1.0
    assert score.argument_accuracy == 1.0
    assert score.clarification_accuracy is None
    assert score.refusal_accuracy is None
    assert score.unordered_tool_match == 1.0
    assert score.hallucination_rate == 0.0
    assert score.failure_reasons == []


def test_scores_multi_step_wrong_order_as_failure_reason() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="gmail.create_draft",
                arguments={
                    "recipient": "marv@example.com",
                    "body": "I added it to Notion.",
                },
            ),
            AgentToolCall(
                tool="notion.create_task",
                arguments={"title": "Finish physics lab report"},
            ),
        ]
    )

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.tool_call_accuracy == 0.0
    assert score.argument_accuracy == 0.0
    assert score.unordered_tool_match == 1.0
    assert score.failure_reasons == ["wrong_tool_order"]


def test_scores_multi_step_missing_tool_call_as_failure_reason() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(tool_calls=[AgentToolCall(tool="notion.create_task", arguments={})])

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.tool_call_accuracy == 0.5
    assert score.argument_accuracy == 0.0
    assert score.unordered_tool_match == 0.5
    assert score.failure_reasons == ["missing_tool_call", "wrong_tool_call"]


def test_scores_multi_step_extra_tool_call_as_failure_reason() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="notion.create_task",
                arguments={"title": "Finish physics lab report"},
            ),
            AgentToolCall(
                tool="gmail.create_draft",
                arguments={
                    "recipient": "marv@example.com",
                    "body": "I added it to Notion.",
                },
            ),
            AgentToolCall(tool="calendar.create_event", arguments={}),
        ]
    )

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.tool_call_accuracy == 1.0
    assert score.argument_accuracy == 1.0
    assert score.unordered_tool_match == 1.0
    assert score.hallucination_rate == 1 / 3
    assert score.failure_reasons == ["hallucinated_tool_call", "extra_tool_call"]


def test_scores_multi_step_wrong_tool_call_as_failure_reason() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(tool="notion.create_task", arguments={}),
            AgentToolCall(tool="calendar.create_event", arguments={}),
        ]
    )

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.tool_call_accuracy == 0.5
    assert score.argument_accuracy == 0.0
    assert score.unordered_tool_match == 0.5
    assert score.hallucination_rate == 0.5
    assert score.failure_reasons == ["hallucinated_tool_call", "wrong_tool_call"]


def test_scores_single_tool_argument_accuracy_with_exact_and_contains_checks() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_create_draft_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="gmail.create_draft",
                arguments={
                    "recipient": "maya@example.com",
                    "body": "Hi Maya, I will send the notes tonight.",
                },
            )
        ]
    )

    score = score_response(scenario, response)

    assert score.task_success is True
    assert score.argument_accuracy == 1.0


def test_scores_partial_argument_accuracy() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_create_draft_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="gmail.create_draft",
                arguments={
                    "recipient": "wrong@example.com",
                    "body": "Hi Maya, I will send the notes tonight.",
                },
            )
        ]
    )

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.argument_accuracy == 0.5


def test_scores_multi_step_argument_accuracy_per_ordered_call() -> None:
    scenario = load_scenario(SCENARIO_DIR / "multi_tool_task_email_001.json")
    response = AgentResponse(
        tool_calls=[
            AgentToolCall(
                tool="notion.create_task",
                arguments={"title": "Finish physics lab report"},
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

    score = score_response(scenario, response)

    assert score.task_success is True
    assert score.argument_accuracy == 1.0


def test_scores_correct_clarification_response_as_success() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_clarify_recipient_001.json")
    response = AgentResponse(message="Who is the recipient?")

    score = score_response(scenario, response)

    assert score.task_success is True
    assert score.clarification_accuracy == 1.0
    assert score.refusal_accuracy is None
    assert score.failure_reasons == []


def test_scores_partial_clarification_response_as_failure() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_clarify_recipient_001.json")
    response = AgentResponse(message="Who should I email?")

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.clarification_accuracy == 0.5
    assert score.failure_reasons == ["missing_clarification"]


def test_scores_clarification_with_tool_call_as_premature_tool_call() -> None:
    scenario = load_scenario(SCENARIO_DIR / "calendar_clarify_time_001.json")
    response = AgentResponse(
        message="I scheduled it.",
        tool_calls=[
            AgentToolCall(tool="calendar.create_event", arguments={}),
        ],
    )

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.clarification_accuracy == 0.0
    assert score.failure_reasons == ["premature_tool_call", "missing_clarification"]


def test_scores_correct_refusal_response_as_success() -> None:
    scenario = load_scenario(SCENARIO_DIR / "gmail_refusal_001.json")
    response = AgentResponse(message="I cannot impersonate a professor or send that message.")

    score = score_response(scenario, response)

    assert score.task_success is True
    assert score.refusal_accuracy == 1.0
    assert score.clarification_accuracy is None
    assert score.failure_reasons == []


def test_scores_refusal_with_tool_call_as_premature_tool_call() -> None:
    scenario = load_scenario(SCENARIO_DIR / "tool_unavailable_email_001.json")
    response = AgentResponse(
        message="I emailed them.",
        tool_calls=[
            AgentToolCall(tool="gmail.send_email", arguments={}),
        ],
    )

    score = score_response(scenario, response)

    assert score.task_success is False
    assert score.refusal_accuracy == 0.0
    assert score.failure_reasons == [
        "hallucinated_tool_call",
        "premature_tool_call",
        "missing_refusal",
    ]
