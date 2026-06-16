"""Score agent responses against BAYMAX evaluation scenarios."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from baymax.eval.scenario_loader import (
    ClarificationExpectedBehavior,
    RefusalExpectedBehavior,
    Scenario,
    ToolCallExpectedBehavior,
    ToolCallsExpectedBehavior,
)

FailureReason = Literal[
    "wrong_tool_order",
    "missing_tool_call",
    "extra_tool_call",
    "hallucinated_tool_call",
    "missing_clarification",
    "missing_refusal",
    "premature_tool_call",
    "wrong_tool_call",
]


class AgentToolCall(BaseModel):
    """One tool call emitted by an agent."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Agent output captured by the eval runner."""

    model_config = ConfigDict(extra="forbid")

    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    message: str | None = None


class ScenarioScore(BaseModel):
    """Deterministic score for one scenario run."""

    model_config = ConfigDict(extra="forbid")

    task_success: bool
    tool_call_accuracy: float
    argument_accuracy: float
    clarification_accuracy: float | None
    refusal_accuracy: float | None
    unordered_tool_match: float
    hallucination_rate: float
    failure_reasons: list[FailureReason] = Field(default_factory=list)


def score_response(scenario: Scenario, response: AgentResponse) -> ScenarioScore:
    """Score an agent response against the scenario's expected behavior."""

    expected_behavior = scenario.expected_behavior
    if isinstance(expected_behavior, ToolCallExpectedBehavior):
        expected_tools = [expected_behavior.tool]
    elif isinstance(expected_behavior, ToolCallsExpectedBehavior):
        expected_tools = [call.tool for call in expected_behavior.calls]
    else:
        expected_tools = []

    actual_tools = [call.tool for call in response.tool_calls]
    available_tools = set(scenario.available_tools)
    failure_reasons = _tool_call_failure_reasons(
        expected_tools=expected_tools,
        actual_tools=actual_tools,
        available_tools=available_tools,
    )
    clarification_accuracy = _clarification_accuracy(expected_behavior, response)
    refusal_accuracy = _refusal_accuracy(expected_behavior, response)

    if isinstance(expected_behavior, ClarificationExpectedBehavior):
        if actual_tools:
            failure_reasons.append("premature_tool_call")
        if clarification_accuracy != 1.0:
            failure_reasons.append("missing_clarification")

    if isinstance(expected_behavior, RefusalExpectedBehavior):
        if actual_tools:
            failure_reasons.append("premature_tool_call")
        if refusal_accuracy != 1.0:
            failure_reasons.append("missing_refusal")

    argument_accuracy = _argument_accuracy(expected_behavior, response.tool_calls)

    hallucinated_tool_count = sum(1 for tool in actual_tools if tool not in available_tools)
    hallucination_rate = (
        hallucinated_tool_count / len(actual_tools) if actual_tools else 0.0
    )

    return ScenarioScore(
        task_success=not failure_reasons and argument_accuracy == 1.0,
        tool_call_accuracy=_ordered_tool_accuracy(expected_tools, actual_tools),
        argument_accuracy=argument_accuracy,
        clarification_accuracy=clarification_accuracy,
        refusal_accuracy=refusal_accuracy,
        unordered_tool_match=_unordered_tool_match(expected_tools, actual_tools),
        hallucination_rate=hallucination_rate,
        failure_reasons=failure_reasons,
    )


def _ordered_tool_accuracy(expected_tools: list[str], actual_tools: list[str]) -> float:
    if not expected_tools:
        return 1.0 if not actual_tools else 0.0

    correct_ordered_tools = sum(
        1
        for index, expected_tool in enumerate(expected_tools)
        if index < len(actual_tools) and actual_tools[index] == expected_tool
    )
    return correct_ordered_tools / len(expected_tools)


def _unordered_tool_match(expected_tools: list[str], actual_tools: list[str]) -> float:
    if not expected_tools:
        return 1.0 if not actual_tools else 0.0

    unmatched_actual_tools = actual_tools.copy()
    matched_tools = 0
    for expected_tool in expected_tools:
        if expected_tool in unmatched_actual_tools:
            matched_tools += 1
            unmatched_actual_tools.remove(expected_tool)

    return matched_tools / len(expected_tools)


def _argument_accuracy(
    expected_behavior: object,
    actual_tool_calls: list[AgentToolCall],
) -> float:
    if isinstance(expected_behavior, ToolCallExpectedBehavior):
        expected_argument_sets = [expected_behavior.arguments]
    elif isinstance(expected_behavior, ToolCallsExpectedBehavior):
        expected_argument_sets = [call.arguments for call in expected_behavior.calls]
    else:
        return 1.0

    total_checks = sum(len(arguments) for arguments in expected_argument_sets)
    if total_checks == 0:
        return 1.0

    correct_checks = 0
    for index, expected_arguments in enumerate(expected_argument_sets):
        actual_arguments = (
            actual_tool_calls[index].arguments if index < len(actual_tool_calls) else {}
        )
        correct_checks += _count_correct_argument_checks(
            expected_arguments=expected_arguments,
            actual_arguments=actual_arguments,
        )

    return correct_checks / total_checks


def _clarification_accuracy(
    expected_behavior: object,
    response: AgentResponse,
) -> float | None:
    if not isinstance(expected_behavior, ClarificationExpectedBehavior):
        return None

    if response.tool_calls:
        return 0.0

    return _keyword_accuracy(
        expected_keywords=expected_behavior.question_contains,
        message=response.message,
    )


def _refusal_accuracy(
    expected_behavior: object,
    response: AgentResponse,
) -> float | None:
    if not isinstance(expected_behavior, RefusalExpectedBehavior):
        return None

    if response.tool_calls:
        return 0.0

    return _keyword_accuracy(
        expected_keywords=expected_behavior.reason_contains,
        message=response.message,
    )


def _keyword_accuracy(*, expected_keywords: list[str], message: str | None) -> float:
    if not expected_keywords:
        return 1.0

    if message is None:
        return 0.0

    normalized_message = message.casefold()
    matched_keywords = sum(
        1 for keyword in expected_keywords if keyword.casefold() in normalized_message
    )
    return matched_keywords / len(expected_keywords)


def _count_correct_argument_checks(
    *,
    expected_arguments: dict[str, Any],
    actual_arguments: dict[str, Any],
) -> int:
    correct_checks = 0
    for key, expected_value in expected_arguments.items():
        if key.endswith("_contains"):
            actual_key = key.removesuffix("_contains")
            actual_value = actual_arguments.get(actual_key)
            if (
                isinstance(expected_value, str)
                and isinstance(actual_value, str)
                and expected_value.casefold() in actual_value.casefold()
            ):
                correct_checks += 1
        elif actual_arguments.get(key) == expected_value:
            correct_checks += 1

    return correct_checks


def _tool_call_failure_reasons(
    *,
    expected_tools: list[str],
    actual_tools: list[str],
    available_tools: set[str],
) -> list[FailureReason]:
    failure_reasons: list[FailureReason] = []

    if any(tool not in available_tools for tool in actual_tools):
        failure_reasons.append("hallucinated_tool_call")

    if not expected_tools:
        return failure_reasons

    if len(actual_tools) < len(expected_tools):
        failure_reasons.append("missing_tool_call")

    if len(actual_tools) > len(expected_tools):
        failure_reasons.append("extra_tool_call")

    if actual_tools[: len(expected_tools)] != expected_tools:
        if sorted(actual_tools[: len(expected_tools)]) == sorted(expected_tools):
            failure_reasons.append("wrong_tool_order")
        elif expected_tools:
            failure_reasons.append("wrong_tool_call")

    return failure_reasons
