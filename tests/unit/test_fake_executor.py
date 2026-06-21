from baymax.eval.fake_executor import execute_tool_calls
from baymax.eval.scorer import AgentToolCall


def test_executes_calendar_create_event() -> None:
    result = execute_tool_calls(
        initial_state={"calendar_events": []},
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
        ],
    )

    assert result.tool_results[0].success is True
    assert result.tool_results[0].tool == "calendar.create_event"
    assert result.final_state["calendar_events"] == [
        {
            "id": "evt_fake_calendar_001",
            "title": "Linear algebra revision",
            "start_date": "2026-05-19",
            "start_time": "16:00",
            "duration_minutes": 120,
        }
    ]


def test_executes_multi_step_clipboard_read_then_notion_create() -> None:
    result = execute_tool_calls(
        initial_state={
            "clipboard": {"text": "Finish ML assignment by Friday"},
            "notion_tasks": [],
        },
        tool_calls=[
            AgentToolCall(tool="clipboard.read", arguments={}),
            AgentToolCall(
                tool="notion.create_task",
                arguments={
                    "title": "Finish ML assignment",
                    "due_date": "2026-05-22",
                },
            ),
        ],
    )

    assert [tool_result.tool for tool_result in result.tool_results] == [
        "clipboard.read",
        "notion.create_task",
    ]
    assert result.tool_results[0].data == {"text": "Finish ML assignment by Friday"}
    assert result.final_state["notion_tasks"] == [
        {
            "id": "task_fake_notion_001",
            "title": "Finish ML assignment",
            "status": "open",
            "due_date": "2026-05-22",
        }
    ]
    assert result.final_state["clipboard"] == {"text": "Finish ML assignment by Friday"}


def test_executes_all_calls_even_after_failure() -> None:
    result = execute_tool_calls(
        initial_state={"calendar_events": [], "notion_tasks": []},
        tool_calls=[
            AgentToolCall(
                tool="calendar.update_event",
                arguments={
                    "event_id": "evt_missing_001",
                    "start_time": "17:00",
                },
            ),
            AgentToolCall(
                tool="notion.create_task",
                arguments={"title": "Submit scholarship form"},
            ),
        ],
    )

    assert result.tool_results[0].success is False
    assert result.tool_results[0].error == "calendar event not found: evt_missing_001"
    assert result.tool_results[1].success is True
    assert result.final_state["notion_tasks"][0]["title"] == "Submit scholarship form"


def test_unknown_tool_returns_failure_result() -> None:
    result = execute_tool_calls(
        initial_state={},
        tool_calls=[
            AgentToolCall(tool="slack.send_message", arguments={}),
        ],
    )

    assert result.tool_results[0].success is False
    assert result.tool_results[0].tool == "slack.send_message"
    assert result.tool_results[0].error == "unknown fake tool: slack.send_message"


def test_invalid_tool_arguments_return_failure_result() -> None:
    result = execute_tool_calls(
        initial_state={"gmail_drafts": []},
        tool_calls=[
            AgentToolCall(
                tool="gmail.create_draft",
                arguments={
                    "recipient": "not-an-email",
                    "body": "I will send the notes tonight.",
                },
            ),
        ],
    )

    assert result.tool_results[0].success is False
    assert result.tool_results[0].tool == "gmail.create_draft"
    assert result.tool_results[0].error is not None
    assert "validation failed for gmail.create_draft" in result.tool_results[0].error
    assert result.final_state["gmail_drafts"] == []
