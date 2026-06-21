"""Agent core — the main orchestration loop.

Per ADR 0001 (Plan-and-Execute with finite ReAct recovery loop).

Loop:
    1. model.plan_task(user_input, available_tools, context) → task_file
    2. validator.validate(task_file)
    3. for each step in task_file.plan:
         dispatch → adapter
         if recoverable error: retry / clarify / abort
    4. model.interpret_results(action_log, user_input) → response_text
    5. return AgentResponse

Per ADR 0002 the agent emits AgentResponse at the boundary; internally it
works with TaskFile.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from baymax.core.contracts import (
    ActionLogEntry,
    AgentResponse,
    CompletionStatus,
    ErrorType,
    InputType,
    RequestComplexity,
    RequestType,
    ResponseType,
    TaskFile,
    ToolCallResult,
    ToolCallStep,
)
from baymax.core.validator import Validator
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    PlanRequest,
)
from baymax.telemetry.logger import TelemetryLogger

# DECISION: ToolDispatcher is a callable type alias rather than an abstract base
# class. Callers pass a function (or a class with __call__) that takes a
# ToolCallStep and returns a ToolCallResult. Keeps the agent decoupled from
# Ronin's adapter implementations.
ToolDispatcher = Callable[[ToolCallStep], Awaitable[ToolCallResult]]


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for one Agent instance."""

    max_retries_per_step: int = 1
    # DECISION: default 1 retry per step. Production agents typically allow 2-3,
    # but for v1 eval we want failures to surface quickly rather than getting
    # masked by retry loops.


class Agent:
    """The agent orchestrator.

    Constructed once per process (or per session). Stateless across requests;
    state lives on each request's TaskFile + telemetry trace.
    """

    def __init__(
        self,
        *,
        inference: InferenceBackend,
        dispatcher: ToolDispatcher,
        validator: Validator | None = None,
        telemetry: TelemetryLogger | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        self._inference = inference
        self._dispatcher = dispatcher
        self._validator = validator or Validator()
        self._telemetry = telemetry or TelemetryLogger.configure()
        self._config = config or AgentConfig()

    async def handle_request(
        self,
        *,
        user_input: str,
        available_tools: list[str],
        context: dict[str, Any] | None = None,
        tool_schemas: dict[str, dict[str, Any]] | None = None,
        run_id: str | None = None,
    ) -> AgentResponse:
        """Handle one user request end-to-end. Returns the boundary AgentResponse.

        Args:
            user_input: the user's request text
            available_tools: tools the scenario permits (per Ronin's scenario.available_tools)
            context: optional context dict (datetime, location, prior task context, etc.)
            tool_schemas: per-tool JSON schemas for argument validation (optional)
            run_id: optional run identifier; auto-generated if absent
        """
        context = context or {}
        tool_schemas = tool_schemas or {}
        run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"

        # task_id format: <run_id>.<task_int>.<phase_int>
        # v1: task_int always 1, phase_int always 0 (sub-tasks deferred to v2)
        task_id = f"{run_id}.1.0"

        with self._telemetry.trace("handle_request", run_id=run_id) as trace:
            trace.task_id = task_id

            # Construct initial task_file. request_type/complexity get filled
            # after planning; placeholder values used here.
            task = TaskFile(
                task_id=task_id,
                request_text=user_input,
                input_type=InputType.TEXT,
                request_type=RequestType.VALIDATION,  # provisional
                request_intent=None,
                request_complexity=RequestComplexity.SINGLE_TOOL,  # provisional
                context=context,
                max_plan_steps=10,
                available_tools=available_tools,
                plan=[],
                started_at=datetime.now(timezone.utc),
            )

            # ----- Phase 1: plan the task -----
            self._telemetry.event(trace, "plan_task_started")
            plan_result = await self._inference.plan_task(
                PlanRequest(
                    user_input=user_input,
                    available_tools=available_tools,
                    context=context,
                    tool_schemas=tool_schemas,
                )
            )
            trace.cost.add_llm(
                input_tokens=plan_result.input_tokens,
                output_tokens=plan_result.output_tokens,
                usd=plan_result.cost_usd,
            )
            self._telemetry.event(
                trace,
                "plan_task_completed",
                intent_unclear=plan_result.intent_unclear,
                refusal=plan_result.refusal_reason is not None,
                plan_length=len(plan_result.plan) if plan_result.plan else 0,
            )

            # Refusal short-circuit
            if plan_result.refusal_reason is not None:
                task.response_text = plan_result.refusal_reason
                task.response_type = ResponseType.TASK_REFUSAL
                task.completion_status = CompletionStatus.REFUSED
                task.completed_at = datetime.now(timezone.utc)
                self._telemetry.event(trace, "request_refused", reason=plan_result.refusal_reason)
                # DECISION: per ADR 0002, refusal emits zero tool_calls + message.
                # Ronin's scorer flags any tool call as `premature_tool_call`.
                return task.to_agent_response()

            # Clarification short-circuit
            if plan_result.intent_unclear:
                task.response_text = plan_result.clarification_question
                task.response_type = ResponseType.CLARIFICATION
                task.completion_status = CompletionStatus.CLARIFICATION_PENDING
                # DECISION: also set error_type = AMBIGUOUS_REQUEST. This is the
                # model's self-reported signal that intent was unclear. Setting
                # it here makes ambiguity-perception a MEASURABLE metric across
                # baselines (compute precision/recall vs scenario.difficulty ==
                # "ambiguous"). Per design discussion 2026-06-20.
                task.error_type = ErrorType.AMBIGUOUS_REQUEST
                task.completed_at = datetime.now(timezone.utc)
                self._telemetry.event(
                    trace,
                    "clarification_requested",
                    question=plan_result.clarification_question,
                    error_type=ErrorType.AMBIGUOUS_REQUEST.value,
                )
                return task.to_agent_response()

            # Plan successful — populate task_file
            assert plan_result.plan is not None
            task.plan = plan_result.plan
            task.request_type = plan_result.request_type or RequestType.VALIDATION
            task.request_complexity = (
                plan_result.request_complexity or RequestComplexity.SINGLE_TOOL
            )
            task.request_intent = "interpreted"  # marker; v2 stores actual intent text

            # ----- Phase 2: validate the plan -----
            validation = self._validator.validate_task_file(task)
            if not validation.ok:
                task.completion_status = CompletionStatus.FAILED
                # DECISION: surface the FIRST validation failure as the error reason.
                # Future telemetry should capture the full failure list.
                first_failure = validation.failures[0]
                task.error_type = first_failure.error_type
                task.error_message = first_failure.message
                task.response_text = f"Could not construct a valid plan: {first_failure.message}"
                task.response_type = ResponseType.TASK_REFUSAL
                task.completed_at = datetime.now(timezone.utc)
                self._telemetry.event(
                    trace,
                    "validation_failed",
                    failure_count=len(validation.failures),
                    first_failure=first_failure.message,
                )
                return task.to_agent_response()

            # ----- Phase 3: execute the plan with finite recovery loop -----
            for step_idx, step in enumerate(task.plan):
                attempt = 0
                while attempt <= self._config.max_retries_per_step:
                    started_at = datetime.now(timezone.utc)
                    self._telemetry.event(
                        trace,
                        "tool_dispatch_started",
                        step_index=step_idx,
                        tool=step.tool,
                        attempt=attempt + 1,
                    )
                    try:
                        result = await self._dispatcher(step)
                    except Exception as exc:
                        # Dispatcher itself crashed (not a tool returning failure)
                        result = ToolCallResult(
                            success=False,
                            tool=step.tool,
                            error=f"dispatcher exception: {exc!r}",
                        )
                    completed_at = datetime.now(timezone.utc)
                    trace.cost.add_tool_call()

                    entry = ActionLogEntry(
                        step=step,
                        result=result,
                        started_at=started_at,
                        completed_at=completed_at,
                        attempt_number=attempt + 1,
                    )
                    task.action_log.append(entry)

                    self._telemetry.event(
                        trace,
                        "tool_dispatch_completed",
                        step_index=step_idx,
                        tool=step.tool,
                        success=result.success,
                        error=result.error,
                        attempt=attempt + 1,
                    )

                    if result.success:
                        break  # step succeeded — move to next step

                    # Step failed. Decide: retry or abort.
                    attempt += 1
                    if attempt > self._config.max_retries_per_step:
                        # Out of retries — abort the request.
                        task.completion_status = CompletionStatus.FAILED
                        task.error_type = ErrorType.TOOL_EXECUTION_ERROR
                        task.error_message = (
                            f"tool '{step.tool}' failed after "
                            f"{self._config.max_retries_per_step + 1} attempts: {result.error}"
                        )
                        task.response_text = (
                            f"I tried to run {step.tool} but it failed: {result.error}"
                        )
                        task.response_type = ResponseType.TASK_REFUSAL
                        task.completed_at = datetime.now(timezone.utc)
                        self._telemetry.event(
                            trace,
                            "step_failed_terminal",
                            step_index=step_idx,
                            tool=step.tool,
                            final_error=result.error,
                        )
                        return task.to_agent_response()

            # ----- Phase 4: all steps succeeded — interpret results -----
            self._telemetry.event(trace, "interpret_results_started")
            summary = _render_action_log_summary(task)
            interpret_result = await self._inference.interpret_results(
                InterpretRequest(user_input=user_input, action_log_summary=summary)
            )
            trace.cost.add_llm(
                input_tokens=interpret_result.input_tokens,
                output_tokens=interpret_result.output_tokens,
                usd=interpret_result.cost_usd,
            )

            task.response_text = interpret_result.response_text
            task.response_type = ResponseType.TASK_DONE
            task.completion_status = CompletionStatus.COMPLETE
            task.completed_at = datetime.now(timezone.utc)

            self._telemetry.event(trace, "request_completed_successfully")
            return task.to_agent_response()


def _render_action_log_summary(task: TaskFile) -> str:
    """Render the action log into a compact summary for the model to interpret.

    Format: one line per step with tool, key args, success/error.
    """
    if not task.action_log:
        return "(no tools were called)"
    lines = []
    for i, entry in enumerate(task.action_log, start=1):
        args_preview = ", ".join(f"{k}={v!r}" for k, v in list(entry.step.arguments.items())[:5])
        status = "OK" if entry.result.success else f"FAILED: {entry.result.error}"
        data_preview = ""
        if entry.result.data:
            data_preview = f" → returned {len(entry.result.data)} field(s): " + ", ".join(
                list(entry.result.data.keys())[:3]
            )
        lines.append(f"{i}. {entry.step.tool}({args_preview}) — {status}{data_preview}")
    return "\n".join(lines)
