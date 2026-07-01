"""Tests for baymax.core.contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from baymax.core.contracts import (
    ActionLogEntry,
    AgentResponse,
    AgentToolCall,
    CompletionStatus,
    InputType,
    RequestComplexity,
    RequestType,
    ResponseType,
    TaskFile,
    ToolCallResult,
    ToolCallStep,
)
from baymax.eval.scorer import (
    AgentResponse as EvalAgentResponse,
)
from baymax.eval.scorer import (
    AgentToolCall as EvalAgentToolCall,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- AgentToolCall / AgentResponse (boundary shapes) ----------


def test_agent_tool_call_accepts_namespaced_tool_name():
    AgentToolCall(tool="calendar.create_event", arguments={"x": 1})


def test_agent_tool_call_rejects_non_namespaced_tool_name():
    with pytest.raises(ValidationError):
        AgentToolCall(tool="not_namespaced", arguments={})


def test_agent_response_empty_is_valid():
    response = AgentResponse()
    assert response.tool_calls == []
    assert response.message is None


def test_agent_response_with_tool_calls_and_message():
    response = AgentResponse(
        tool_calls=[AgentToolCall(tool="notion.create_task", arguments={"title": "X"})],
        message="Created task.",
    )
    assert len(response.tool_calls) == 1
    assert response.message == "Created task."


def test_agent_response_matches_scorer_shape():
    """Core and eval AgentResponse models must remain mutually compatible."""

    core_response = AgentResponse(
        tool_calls=[AgentToolCall(tool="calendar.create_event", arguments={"title": "x"})],
        message="hi",
    )
    eval_response = EvalAgentResponse(
        tool_calls=[EvalAgentToolCall(tool="calendar.create_event", arguments={"title": "x"})],
        message="hi",
    )

    assert EvalAgentResponse.model_validate(core_response.model_dump()) == eval_response
    assert AgentResponse.model_validate(eval_response.model_dump()) == core_response


# ---------- TaskFile ----------


def _minimal_task() -> TaskFile:
    return TaskFile(
        task_id="run_test.1.0",
        request_text="do a thing",
        input_type=InputType.TEXT,
        request_type=RequestType.CREATION,
        request_complexity=RequestComplexity.SINGLE_TOOL,
        available_tools=["notion.create_task", "calendar.create_event"],
    )


def test_taskfile_minimal_valid():
    task = _minimal_task()
    assert task.task_id == "run_test.1.0"
    assert task.plan == []
    assert task.action_log == []


def test_taskfile_rejects_duplicate_available_tools():
    with pytest.raises(ValidationError):
        TaskFile(
            task_id="run_test.1.0",
            request_text="x",
            request_type=RequestType.CREATION,
            request_complexity=RequestComplexity.SINGLE_TOOL,
            available_tools=["notion.create_task", "notion.create_task"],
        )


def test_taskfile_rejects_non_namespaced_tool_in_available():
    with pytest.raises(ValidationError):
        TaskFile(
            task_id="run_test.1.0",
            request_text="x",
            request_type=RequestType.CREATION,
            request_complexity=RequestComplexity.SINGLE_TOOL,
            available_tools=["not_namespaced"],
        )


def test_taskfile_tools_called_and_success_lists_parallel():
    task = _minimal_task()
    task.action_log = [
        ActionLogEntry(
            step=ToolCallStep(tool="notion.create_task", arguments={"title": "x"}),
            result=ToolCallResult(success=True, tool="notion.create_task"),
            started_at=_now(),
            completed_at=_now(),
        ),
        ActionLogEntry(
            step=ToolCallStep(tool="calendar.create_event", arguments={}),
            result=ToolCallResult(success=False, tool="calendar.create_event", error="boom"),
            started_at=_now(),
            completed_at=_now(),
        ),
    ]
    assert task.tools_called == ["notion.create_task", "calendar.create_event"]
    assert task.tool_call_success == [True, False]


def test_taskfile_to_agent_response_emits_attempted_calls():
    task = _minimal_task()
    task.action_log = [
        ActionLogEntry(
            step=ToolCallStep(tool="notion.create_task", arguments={"title": "x"}),
            result=ToolCallResult(success=True, tool="notion.create_task"),
            started_at=_now(),
            completed_at=_now(),
        )
    ]
    task.response_text = "Created your task."
    response = task.to_agent_response()
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "notion.create_task"
    assert response.message == "Created your task."


def test_taskfile_to_agent_response_clarification_emits_no_tool_calls():
    """Per ADR 0002: clarification + refusal scenarios emit empty tool_calls."""
    task = _minimal_task()
    task.action_log = []  # nothing was attempted
    task.response_text = "Did you mean today or tomorrow?"
    task.response_type = ResponseType.CLARIFICATION
    task.completion_status = CompletionStatus.CLARIFICATION_PENDING
    response = task.to_agent_response()
    assert response.tool_calls == []
    assert response.message == "Did you mean today or tomorrow?"
