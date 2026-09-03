"""Data models for the agent core.

Two layers of types:

1. **External (boundary) types** — `AgentToolCall`, `AgentResponse` — match
   Ronin's `scorer.py` shapes EXACTLY. These are what the eval harness consumes.

2. **Internal types** — `TaskFile`, `ToolCallStep`, `ActionLogEntry`, etc. —
   are the agent's working representation while a request is in flight.
   Never serialised to the eval boundary; always converted via
   `TaskFile.to_agent_response()`.

Per ADR 0002 (tool-call schema).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# DECISION: namespaced lowercase tool naming. Matches Ronin's scorer regex and
# the convention his fake adapters use. Don't loosen this — it's the boundary
# pattern check.
TOOL_NAME_PATTERN = r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"


# ---------------------------------------------------------------------------
# External (boundary) types — match Ronin's scorer.py EXACTLY.
# DECISION: duplicated here rather than imported from baymax.eval.scorer
# because core should not depend on eval. If the shapes drift, tests will
# catch it (see tests/unit/test_contracts.py::test_agent_response_matches_scorer).
# Phase 2 work item: move these to a shared baymax.types package and have both
# core and eval import from there.
# ---------------------------------------------------------------------------


class AgentToolCall(BaseModel):
    """One tool call emitted by the agent. Boundary shape — must match scorer."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(pattern=TOOL_NAME_PATTERN)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Agent output captured by the eval runner. Boundary shape — must match scorer."""

    model_config = ConfigDict(extra="forbid")

    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    message: str | None = None


# ---------------------------------------------------------------------------
# Internal types — agent's working representation.
# ---------------------------------------------------------------------------


class InputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class RequestType(str, Enum):
    """Per ADR 0002."""

    VALIDATION = "validation"  # clarification_pending basically
    CREATION = "creation"
    EDIT = "edit"
    DELETE = "delete"


class RequestComplexity(str, Enum):
    """Per ADR 0002. MULTIPHASE deferred to v2 (irreversible-tool handling)."""

    SINGLE_TOOL = "single_tool"
    MULTI_TOOL = "multi_tool"
    # v2 only — placeholder for completeness. This will most likely be broken
    # down into multiphase single-tool and multiphase multi-tool in v2.
    # For now, the agent core will treat it as the same.
    MULTIPHASE = "multiphase"


class CompletionStatus(str, Enum):
    COMPLETE = "complete"
    # in v2 this will be a separate response_type trigger,
    # but for now we need it as "complete" for scoring.md plans
    CLARIFICATION_PENDING = "clarification_pending"
    ABORTED = "aborted"
    FAILED = "failed"
    REFUSED = "refused"


class ResponseType(str, Enum):
    """Per ADR 0002. task_success is intentionally NOT in this enum — it's a
    post-hoc field populated by Ronin's scorer, not the agent."""

    TASK_DONE = "task_done"
    CLARIFICATION = "clarification"
    TASK_REFUSAL = "task_refusal"
    TASK_ONGOING = "task_ongoing"  # for streaming workflows for user live


class ErrorType(str, Enum):
    """Runtime failure types AND model self-reported signals.

    Two categories:
    1. Hard runtime failures the agent caught (auth, types, timeouts, validation,
       tool-execution failures). These have well-defined recovery paths.
    2. Model-self-reported confidence signals (AMBIGUOUS_REQUEST). These are
       *measurable model capabilities* — used by the eval to score ambiguity
       perception across baselines.

    NOT in this enum:
    - INTENT_ERROR (model picked wrong tool despite confidence): the agent
      cannot detect this at runtime — only Ronin's scorer can flag it via
      comparison to scenario.expected_behavior. Lives in scorer
      `failure_reasons`, not here.
    - REFUSAL / CLARIFICATION as outcomes: these are ResponseType values, not
      errors. They MAY have an associated ErrorType (e.g., AMBIGUOUS_REQUEST
      causes CLARIFICATION) but the outcome itself is not an error.
    """

    # ----- Hard runtime failures (agent caught) -----
    AUTH_ERROR = "auth_error"  # 401/403, missing/expired credential
    ARGUMENT_TYPE_ERROR = "argument_type"  # tool args failed type/shape check
    PLAN_VALIDATION_ERROR = "plan_validation"  # plan failed contract (bad tool, over cap)
    TOOL_EXECUTION_ERROR = "tool_execution"  # adapter returned success=False
    TOOL_TIMEOUT = "tool_timeout"  # adapter exceeded timeout
    INFERENCE_TIMEOUT = "inference_timeout"  # LLM API exceeded timeout
    # Backend failure (retry exhausted OR non-retriable) — see ADR 0011 §E2.
    BACKEND_ERROR = "backend_error"

    # ----- Model-self-reported signals (measurable capabilities) -----
    AMBIGUOUS_REQUEST = "ambiguous_request"  # model recognised intent ambiguity


class ToolCallStep(BaseModel):
    """One step in a task_file's plan (internal representation)."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(pattern=TOOL_NAME_PATTERN)
    arguments: dict[str, Any] = Field(default_factory=dict)
    # DECISION: idempotency key is generated by the agent core from
    # (tool, arguments) hash at dispatch time, not stored on the plan itself.
    # Keeps the plan pure and deterministic.


class ToolCallResult(BaseModel):
    """Result of one tool execution. Mirrors fake_base.FakeToolResult intentionally
    so the agent can consume both fake and (future) real adapter outputs uniformly."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    tool: str
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ActionLogEntry(BaseModel):
    """One (tool_call, result, timing) tuple in the action log."""

    model_config = ConfigDict(extra="forbid")

    step: ToolCallStep
    result: ToolCallResult
    started_at: datetime
    completed_at: datetime
    attempt_number: int = 1  # incremented by recovery logic on retry


class TaskFile(BaseModel):
    """The agent's internal request representation. Constructed at request start,
    mutated only during execution (action_log grows). NOT serialised to eval boundary.

    Per ADR 0002 §2.
    """

    model_config = ConfigDict(extra="forbid")

    # ----- identity -----
    # hierarchical: <run_id / the eval round basically>.<task_int>.<phase_int
    # for multiphase/clarification stuff>, e.g. "run_42.1.0"
    task_id: str

    # ----- input fields -----
    request_text: str = Field(min_length=1)
    input_type: InputType = InputType.TEXT
    request_type: RequestType
    request_intent: str | None = None  # None → triggers clarification (per ADR 0001)
    request_complexity: RequestComplexity
    context: dict[str, Any] = Field(default_factory=dict)
    max_plan_steps: int = Field(default=10, ge=1)  # step-count budget for the plan
    # NOTE: this is NOT wall-clock time — it caps how many tool calls the model
    # can emit in one plan. Per-tool / per-request wall-clock timeouts are a v2
    # concern (see DEFERRED.md).
    available_tools: list[str] = Field(min_length=1)
    plan: list[ToolCallStep] = Field(default_factory=list)

    # ----- output fields (populated during/after execution) -----
    response_text: str | None = None
    completion_status: CompletionStatus | None = None
    response_type: ResponseType | None = None
    action_log: list[ActionLogEntry] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_type: ErrorType | None = None
    error_message: str | None = None

    # NOTE: task_success and cost live on the RunCost / scorer side, not here.
    # The agent only knows "did I terminate cleanly" (completion_status).

    @field_validator("available_tools")
    @classmethod
    def _tools_unique_and_namespaced(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("available_tools entries must be unique")
        import re

        for tool in v:
            if not re.match(TOOL_NAME_PATTERN, tool):
                raise ValueError(f"tool '{tool}' does not match required pattern")
        return v

    @property
    def tools_called(self) -> list[str]:
        """Names of tools in execution order. Read-only convenience for telemetry."""
        return [entry.step.tool for entry in self.action_log]

    @property
    def tool_call_success(self) -> list[bool]:
        """Parallel to tools_called; True/False per attempted call."""
        return [entry.result.success for entry in self.action_log]

    def to_agent_response(self) -> AgentResponse:
        """Convert internal task_file to the boundary shape Ronin's scorer expects.

        Only emits tool_calls that were actually attempted (from action_log),
        not the original plan. For clarification/refusal: emits empty tool_calls.
        """
        # DECISION: emit attempted calls, not planned calls. If the agent
        # decided not to dispatch step 3 (e.g., aborted after step 2 failed),
        # step 3 should NOT appear in the boundary response.
        boundary_calls = [
            AgentToolCall(tool=entry.step.tool, arguments=entry.step.arguments)
            for entry in self.action_log
        ]
        return AgentResponse(
            tool_calls=boundary_calls,
            message=self.response_text,
        )
