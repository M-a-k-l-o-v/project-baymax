"""Tests for baymax.core.validator."""

from __future__ import annotations

from baymax.core.contracts import (
    ErrorType,
    InputType,
    RequestComplexity,
    RequestType,
    TaskFile,
    ToolCallStep,
)
from baymax.core.validator import Validator


def _task_with_plan(plan_tools: list[str], max_plan_steps: int = 10) -> TaskFile:
    return TaskFile(
        task_id="run_test.1.0",
        request_text="x",
        input_type=InputType.TEXT,
        request_type=RequestType.CREATION,
        request_complexity=RequestComplexity.SINGLE_TOOL,
        available_tools=["notion.create_task", "calendar.create_event"],
        max_plan_steps=max_plan_steps,
        plan=[ToolCallStep(tool=t, arguments={}) for t in plan_tools],
    )


def test_validator_accepts_valid_plan():
    task = _task_with_plan(["notion.create_task"])
    result = Validator().validate_task_file(task)
    assert result.ok
    assert result.failures == ()


def test_validator_rejects_plan_referencing_unavailable_tool():
    task = _task_with_plan(["gmail.send_email"])  # not in available_tools
    result = Validator().validate_task_file(task)
    assert not result.ok
    assert result.failures[0].error_type == ErrorType.PLAN_VALIDATION_ERROR
    assert "gmail.send_email" in result.failures[0].message


def test_validator_rejects_plan_exceeding_max_steps():
    task = _task_with_plan(["notion.create_task"] * 5, max_plan_steps=3)
    result = Validator().validate_task_file(task)
    assert not result.ok
    assert any(f.error_type == ErrorType.PLAN_VALIDATION_ERROR for f in result.failures)


def test_validator_validate_tool_call_unavailable_tool():
    result = Validator().validate_tool_call(
        ToolCallStep(tool="gmail.send_email", arguments={}),
        available_tools=["notion.create_task"],
    )
    assert not result.ok
    assert result.failures[0].error_type == ErrorType.PLAN_VALIDATION_ERROR


def test_validator_validate_tool_call_accepts_available_tool():
    result = Validator().validate_tool_call(
        ToolCallStep(tool="notion.create_task", arguments={"title": "x"}),
        available_tools=["notion.create_task"],
    )
    assert result.ok
