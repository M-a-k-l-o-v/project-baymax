"""Validator class — checks task_files and tool calls against the contract.

Separated from TaskFile per SOLID Single Responsibility (decision in
class-diagram refactor, locked 2026-06-17).

Per ADR 0002.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from baymax.core.contracts import (
    ErrorType,
    TaskFile,
    ToolCallStep,
)


@dataclass(frozen=True)
class ValidationFailure:
    """One validation problem. Multiple may be returned per check."""

    error_type: ErrorType
    message: str
    field: str | None = None  # which field failed, when known


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a validation check."""

    ok: bool
    failures: tuple[ValidationFailure, ...] = ()

    @classmethod
    def passed(cls) -> "ValidationResult":
        return cls(ok=True)

    @classmethod
    def failed(cls, *failures: ValidationFailure) -> "ValidationResult":
        return cls(ok=False, failures=failures)


class Validator:
    """Validates task_files and individual tool calls.

    Stateless — instances are cheap. The agent core constructs one per request
    or holds a singleton. No async needed; validation is pure computation.
    """

    # im still considering the null logic — what if it returns "i dont know" or
    # something like that in the request_intent feild??? needs more thought,
    # maybe non-confident answer should just be null
    def validate_task_file(self, task: TaskFile) -> ValidationResult:
        """Validate a constructed task_file before any tool dispatches.

        Checks:
        - request_intent must be populated (null triggers clarification, NOT validation failure)
        - plan length must not exceed max_plan_steps

        Pydantic handles field-level shape validation at construction; this
        method does semantic / cross-field validation.
        """
        failures: list[ValidationFailure] = []

        # DECISION: request_intent == None is NOT a validation failure here.
        # It's a signal that the agent should produce a clarification response.
        # The agent loop handles that path; validator only flags malformed plans.

        # Plan must reference only available tools (no hallucinated tools)
        available = set(task.available_tools)
        for i, step in enumerate(task.plan):
            if step.tool not in available:
                failures.append(
                    ValidationFailure(
                        error_type=ErrorType.PLAN_VALIDATION_ERROR,
                        message=(
                            f"plan step {i} calls '{step.tool}' which is not in available_tools"
                        ),
                        field=f"plan[{i}].tool",
                    )
                )

        # Plan length must not exceed max_plan_steps (step-count budget, NOT wall-clock time)
        if len(task.plan) > task.max_plan_steps:
            failures.append(
                ValidationFailure(
                    error_type=ErrorType.PLAN_VALIDATION_ERROR,
                    message=(
                        f"plan has {len(task.plan)} steps, "
                        f"exceeds max_plan_steps={task.max_plan_steps}"
                    ),
                    field="plan",
                )
            )

        if failures:
            return ValidationResult.failed(*failures)
        return ValidationResult.passed()

    def validate_tool_call(
        self,
        step: ToolCallStep,
        *,
        available_tools: list[str],
        tool_schemas: dict[str, dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """Validate one tool call before dispatch.

        Args:
            step: the tool call to validate
            available_tools: tools this scenario permits
            tool_schemas: optional per-tool JSON schemas for argument validation.
                If provided, the call's arguments are validated against the schema
                for step.tool. If None, only tool name is checked.
        """
        failures: list[ValidationFailure] = []

        if step.tool not in available_tools:
            failures.append(
                ValidationFailure(
                    error_type=ErrorType.PLAN_VALIDATION_ERROR,
                    message=f"tool '{step.tool}' is not in available_tools",
                    field="tool",
                )
            )
            return ValidationResult.failed(*failures)

        if tool_schemas is not None and step.tool in tool_schemas:
            # DECISION: defer real JSON Schema argument validation to v2.
            # For v1, just check that arguments is a dict (which pydantic
            # already enforces). When tool_schemas is wired up properly,
            # use jsonschema.validate here.
            pass

        if failures:
            return ValidationResult.failed(*failures)
        return ValidationResult.passed()
