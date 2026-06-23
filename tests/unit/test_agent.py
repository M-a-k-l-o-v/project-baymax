"""Tests for baymax.core.agent — the orchestration loop.

Uses a fake InferenceBackend so tests don't hit OpenAI.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from baymax.core.agent import Agent, AgentConfig
from baymax.core.contracts import ToolCallResult, ToolCallStep
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
)


@dataclass
class FakeBackend(InferenceBackend):
    """Test double for InferenceBackend that returns canned responses."""

    plan_response: PlanResult
    interpret_response: InterpretResult = InterpretResult(
        response_text="ok done", input_tokens=5, output_tokens=3
    )

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        return self.plan_response

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        return self.interpret_response


async def _ok_dispatcher(step: ToolCallStep) -> ToolCallResult:
    return ToolCallResult(success=True, tool=step.tool, data={"id": "fake_123"})


async def _failing_dispatcher(step: ToolCallStep) -> ToolCallResult:
    return ToolCallResult(success=False, tool=step.tool, error="boom")


@pytest.mark.asyncio
async def test_agent_happy_path_single_tool():
    backend = FakeBackend(
        plan_response=PlanResult(
            plan=[ToolCallStep(tool="notion.create_task", arguments={"title": "x"})],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
            input_tokens=20,
            output_tokens=10,
            cost_usd=0.0001,
        )
    )
    agent = Agent(inference=backend, dispatcher=_ok_dispatcher)
    response = await agent.handle_request(
        user_input="Create a task to buy milk",
        available_tools=["notion.create_task"],
    )
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool == "notion.create_task"
    assert response.message == "ok done"


@pytest.mark.asyncio
async def test_agent_clarification_emits_no_tool_calls():
    backend = FakeBackend(
        plan_response=PlanResult(
            plan=None,
            intent_unclear=True,
            request_type=None,
            request_complexity=None,
            clarification_question="Did you mean today or tomorrow?",
            refusal_reason=None,
        )
    )
    agent = Agent(inference=backend, dispatcher=_ok_dispatcher)
    response = await agent.handle_request(
        user_input="something ambiguous",
        available_tools=["notion.create_task"],
    )
    # Per ADR 0002 clarification emits empty tool_calls + message
    assert response.tool_calls == []
    assert response.message == "Did you mean today or tomorrow?"


@pytest.mark.asyncio
async def test_agent_refusal_emits_no_tool_calls():
    backend = FakeBackend(
        plan_response=PlanResult(
            plan=None,
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason="Out of scope",
        )
    )
    agent = Agent(inference=backend, dispatcher=_ok_dispatcher)
    response = await agent.handle_request(
        user_input="hack a server",
        available_tools=["notion.create_task"],
    )
    assert response.tool_calls == []
    assert response.message == "Out of scope"


@pytest.mark.asyncio
async def test_agent_validation_failure_emits_refusal():
    # Plan references a tool not in available_tools — validator should reject.
    backend = FakeBackend(
        plan_response=PlanResult(
            plan=[ToolCallStep(tool="gmail.send_email", arguments={})],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    agent = Agent(inference=backend, dispatcher=_ok_dispatcher)
    response = await agent.handle_request(
        user_input="send mail",
        available_tools=["notion.create_task"],  # gmail not allowed
    )
    assert response.tool_calls == []
    assert response.message is not None
    msg = response.message.lower()
    assert "valid plan" in msg or "not in available" in msg


@pytest.mark.asyncio
async def test_agent_step_failure_terminates_with_failure_message():
    backend = FakeBackend(
        plan_response=PlanResult(
            plan=[ToolCallStep(tool="notion.create_task", arguments={"title": "x"})],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    agent = Agent(
        inference=backend,
        dispatcher=_failing_dispatcher,
        config=AgentConfig(max_retries_per_step=0),  # fail fast for test
    )
    response = await agent.handle_request(
        user_input="create task",
        available_tools=["notion.create_task"],
    )
    # The failed attempt IS included in tool_calls (we attempted it)
    assert len(response.tool_calls) == 1
    msg = (response.message or "").lower()
    assert "failed" in msg or "boom" in msg


@pytest.mark.asyncio
async def test_agent_multi_tool_plan_executes_in_order():
    backend = FakeBackend(
        plan_response=PlanResult(
            plan=[
                ToolCallStep(tool="clipboard.read", arguments={}),
                ToolCallStep(tool="notion.create_task", arguments={"title": "from clipboard"}),
            ],
            intent_unclear=False,
            request_type=None,
            request_complexity=None,
            clarification_question=None,
            refusal_reason=None,
        )
    )
    call_order: list[str] = []

    async def recording_dispatcher(step: ToolCallStep) -> ToolCallResult:
        call_order.append(step.tool)
        return ToolCallResult(success=True, tool=step.tool, data={})

    agent = Agent(inference=backend, dispatcher=recording_dispatcher)
    response = await agent.handle_request(
        user_input="save the clip as a task",
        available_tools=["clipboard.read", "notion.create_task"],
    )
    assert call_order == ["clipboard.read", "notion.create_task"]
    assert len(response.tool_calls) == 2
