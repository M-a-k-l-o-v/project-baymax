"""Inference service — abstracts the LLM backend behind a uniform interface.

Per ADR 0005 (v1 abstraction) and ADR 0011 (v2 iteration).

Concrete backends (one per transport):
- `OpenAIBackend` — hits OpenAI HTTPS API. Handles all OpenAI-served models.
- `MLXBackend` — local Apple-Silicon inference. Handles Qwen variants + LoRA adapters.
- (v3+) `AnthropicBackend` — deferred.

Uniformity principle (ADR 0011 §7 + METHODOLOGY): the Agent calls
`plan_task()` / `interpret_results()` and never branches on backend type.
Per-transport format shims live inside the backend. Descriptive metadata
(`max_context`, `cost_model`, `provider`) is exposed for telemetry, NOT
consumed by agent logic.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeGuard, TypeVar, cast

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessageFunctionToolCall,
        ChatCompletionMessageToolCallUnion,
        ChatCompletionToolUnionParam,
    )

from baymax.core.contracts import (
    RequestComplexity,
    RequestType,
    ToolCallStep,
)
from baymax.core.exceptions import (
    BackendConfigError,
    BackendError,
    RetryAttempt,
    _describe_exception,
    is_retriable_api_error,
)

# Module-level logger for retry / warmup telemetry. Tests capture via `caplog`.
_backend_logger = logging.getLogger("baymax.backend")

# Retry policy constants (per ADR 0011 §D — hardcoded, not configurable).
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 1.0
_RETRY_FACTOR = 2.0
_RETRY_JITTER = 0.25  # ±25% random jitter

T = TypeVar("T")

# DECISION: OpenAI function names cannot contain dots, but our tool naming
# convention requires dots ("calendar.create_event"). Mapping: dot → "__".
# Tools come in as "calendar.create_event", get sent to OpenAI as
# "calendar__create_event", and the response is reverse-mapped back.
# Double underscore is unlikely to collide with real tool names that use
# single underscore (e.g., "create_task").
_OPENAI_DOT_REPLACEMENT = "__"


def _to_openai_name(tool_name: str) -> str:
    """Convert dotted tool name to OpenAI-safe function name."""
    return tool_name.replace(".", _OPENAI_DOT_REPLACEMENT)


def _from_openai_name(openai_name: str) -> str:
    """Convert OpenAI-safe function name back to dotted tool name."""
    return openai_name.replace(_OPENAI_DOT_REPLACEMENT, ".")


@dataclass(frozen=True)
class PlanRequest:
    """Input to the planning step."""

    user_input: str
    available_tools: list[str]
    context: dict[str, Any]
    tool_schemas: dict[str, dict[str, Any]]  # per-tool JSON schema for arguments


@dataclass(frozen=True)
class PlanResult:
    """Output of the planning step."""

    # DECISION: planning step returns either a plan OR an intent_unclear marker.
    # The agent loop decides what to do (clarification vs execute) based on which.
    plan: list[ToolCallStep] | None
    intent_unclear: bool
    request_type: RequestType | None
    request_complexity: RequestComplexity | None
    clarification_question: str | None  # populated when intent_unclear
    refusal_reason: str | None  # populated when model decides to refuse
    # Cost telemetry passed through to caller
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class InterpretRequest:
    """Input to the result-interpretation step."""

    user_input: str
    action_log_summary: str  # pre-rendered summary of what happened


@dataclass(frozen=True)
class InterpretResult:
    response_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Abstract backend interface
# ---------------------------------------------------------------------------


class InferenceBackend(ABC):
    """Swappable LLM backend. One class per TRANSPORT (not per model).

    Concrete subclasses (per ADR 0011 §1):
    - `OpenAIBackend` — one class, handles all OpenAI-served models via model_id.
    - `MLXBackend` — one class, handles all locally-served MLX variants via model_id.

    Attributes (populated by subclass __init__):
    - `model_id`: which specific model within this transport (e.g., "gpt-4o-mini").
    - `provider`: transport identifier ("openai" | "mlx" | "anthropic"). Used for
      telemetry filtering; NOT consumed by agent logic (uniformity per §7).
    - `max_context`: context window in tokens. Advisory (telemetry / debug only).
    - `cost_model`: "per_token" for API backends, "amortized" for local MLX.
      Consumed by cost accounting reporting; not by agent branching.

    Subclasses call `super().__init__(model_id)` to bind `model_id`, then set
    the other attributes based on the specific model.
    """

    # Class-level defaults — subclasses override in __init__.
    provider: str = "unknown"
    max_context: int = 0
    cost_model: str = "amortized"

    def __init__(self, model_id: str = "unknown") -> None:
        # DECISION: default "unknown" is a test convenience — production callers
        # (FastAPI lifespan) always pass an explicit model_id from env, and
        # concrete backends validate against their own registry lookups.
        # Tests that don't care about model identity can just call `FakeBackend()`.
        self.model_id = model_id

    @abstractmethod
    async def plan_task(self, request: PlanRequest) -> PlanResult:
        """Construct a tool-call plan from user input + available tools."""

    @abstractmethod
    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        """Convert raw tool outputs into a user-facing response message."""

    async def warmup(self) -> None:
        """Backend warmup — run a dummy scenario to force compilation / weight load.

        Called during FastAPI lifespan startup per ADR 0011 §C. Default
        implementation is a no-op (adequate for API backends where there's
        nothing to compile locally). `MLXBackend` overrides to force Metal
        kernel compilation via a real inference call.

        On failure, raises `WarmupFailure` — uvicorn exits at startup per §C3.
        """
        # Default: nothing to warm.
        return None

    # ------------------------------------------------------------------
    # Retry helper — base-class implementation, shared across backends.
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        make_request: Callable[[], Awaitable[T]],
        *,
        telemetry_kind: str = "backend_call",
        retriable_classifier: Callable[[BaseException], tuple[bool, str]] | None = None,
        max_attempts: int = _RETRY_MAX_ATTEMPTS,
    ) -> T:
        """Retry wrapper for LLM API calls.

        Per ADR 0011 §D:
        - `max_attempts` = 3 (hardcoded default; overridable per-call).
        - Exponential backoff: 1s, 2s, 4s with ±25% jitter.
        - `retriable_classifier` decides which errors retry vs fail-fast. Defaults
          to `is_retriable_api_error` (HTTP-oriented). MLX backend passes a
          classifier that returns `(False, "mlx_deterministic")` for everything,
          effectively disabling retry per §D3.
        - Emits per-attempt + final-aggregate telemetry per §D5.
        - On exhaustion or non-retriable error: raises `BackendError` wrapping
          the last exception (§E1).

        Callers pass an async closure that performs one API request. Do NOT
        wrap non-idempotent operations (e.g., tool dispatch) — retry-safe only.
        """
        classifier = retriable_classifier or is_retriable_api_error
        attempts: list[RetryAttempt] = []

        for attempt in range(1, max_attempts + 1):
            _backend_logger.info(
                "backend_attempt",
                extra={
                    "event": "backend_attempt",
                    "kind": telemetry_kind,
                    "attempt": attempt,
                    "backend": self.provider,
                    "model_id": self.model_id,
                    "is_warmup": telemetry_kind == "warmup",
                },
            )
            try:
                result = await make_request()
            except BaseException as exc:  # noqa: BLE001 — deliberate catch-all so we can classify
                retriable, cause = classifier(exc)
                attempts.append(
                    RetryAttempt(
                        attempt=attempt,
                        delay_before_ms=0,
                        cause=cause,
                        underlying_repr=repr(exc),
                    )
                )

                if not retriable or attempt >= max_attempts:
                    kind = "retry_exhausted" if retriable else "non_retriable"
                    _backend_logger.info(
                        "backend_call_complete",
                        extra={
                            "event": "backend_call_complete",
                            "kind": telemetry_kind,
                            "backend": self.provider,
                            "model_id": self.model_id,
                            "total_attempts": attempt,
                            "final_status": "failed",
                            "failure_kind": kind,
                            "attempts": [a.__dict__ for a in attempts],
                            "underlying": _describe_exception(exc),
                        },
                    )
                    raise BackendError(
                        kind=kind,
                        message=(
                            f"{self.provider} backend failed after {attempt} attempt(s): {cause}"
                        ),
                        underlying=exc,
                        attempts_history=attempts,
                        backend=self.provider,
                    ) from exc

                delay = _compute_backoff_delay_s(attempt)
                attempts[-1] = RetryAttempt(
                    attempt=attempt,
                    delay_before_ms=int(delay * 1000),
                    cause=cause,
                    underlying_repr=repr(exc),
                )
                _backend_logger.info(
                    "backend_retry",
                    extra={
                        "event": "backend_retry",
                        "kind": telemetry_kind,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "delay_before_ms": int(delay * 1000),
                        "cause": cause,
                        "backend": self.provider,
                        "model_id": self.model_id,
                    },
                )
                await asyncio.sleep(delay)
                continue

            # Success path.
            _backend_logger.info(
                "backend_call_complete",
                extra={
                    "event": "backend_call_complete",
                    "kind": telemetry_kind,
                    "backend": self.provider,
                    "model_id": self.model_id,
                    "total_attempts": attempt,
                    "final_status": "success",
                    "attempts": [a.__dict__ for a in attempts],
                },
            )
            return result

        # Unreachable — loop exits via return or raise above.
        raise BackendError(  # pragma: no cover
            kind="unreachable",
            message="_call_llm exhausted retry loop without returning or raising",
            backend=self.provider,
        )


def _compute_backoff_delay_s(attempt: int) -> float:
    """Exponential backoff with jitter (per ADR 0011 §D2).

    `attempt` is 1-indexed and identifies the JUST-FAILED attempt. The returned
    delay is what we sleep BEFORE the next attempt fires. Per §D2 spec:

        attempt=1 failed → sleep 1s → attempt=2
        attempt=2 failed → sleep 2s → attempt=3
        attempt=3 failed → (no retry, exhausted)

    Formula: `base * (factor ** (attempt - 1))` so the FIRST wait is `base * 1 = 1s`.
    Then jittered by ±25% to prevent synchronized retries across parallel eval batches.
    """
    base_delay = _RETRY_BASE_DELAY_S * (_RETRY_FACTOR ** (attempt - 1))
    jitter_multiplier = 1.0 + random.uniform(-_RETRY_JITTER, _RETRY_JITTER)  # noqa: S311 — jitter, not crypto
    return max(0.0, base_delay * jitter_multiplier)


# ---------------------------------------------------------------------------
# OpenAI backend (v1 default)
# ---------------------------------------------------------------------------

# DECISION: gpt-4o-mini is the default for v1. It supports function-calling
# natively, costs ~$0.15/1M input + $0.60/1M output (mid-2026 pricing), and
# is well-tested for tool-call extraction. Swap to gpt-4o for harder
# scenarios when we measure model-capacity-bound failures.
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

# Pricing per million tokens (USD). Update when OpenAI changes pricing.
# DECISION: hardcoded here for v1. v2 moves to a ModelPricing class
# (per class-diagram refactor) sourced from a config file.
_OPENAI_PRICING_PER_MTOK = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


_PLAN_SYSTEM_PROMPT = (
    "You are BAYMAX, a personal-task agent. The user will give you a request.\n"
    "You have access to a fixed set of tools. Your job:\n\n"
    "1. Decide if you understand the user's intent. If NOT, call the special function\n"
    "   `request_clarification` with a question.\n"
    "2. Decide if the request is OUT OF SCOPE (e.g., asking you to do something not\n"
    "   supported by available tools, or harmful). If so, call `refuse_request` with\n"
    "   a reason.\n"
    "3. Otherwise, emit one or more tool calls (in execution order) that satisfy the\n"
    "   request.\n\n"
    "Rules:\n"
    "- Never invent tool names. Use only the tools listed.\n"
    "- Prefer fewer tool calls when possible.\n"
    "- For multi-step requests, emit calls in the order they should execute.\n"
    "- If the user's request is ambiguous (could mean multiple things), prefer\n"
    "  asking for clarification over guessing.\n\n"
    "Current context (provided by the agent runtime, not by the user):\n"
    "{context_block}\n"
)


_INTERPRET_SYSTEM_PROMPT = (
    "You are BAYMAX. Given the user's original request and a log of what tools "
    "were called and their results, write a concise natural-language response "
    "to the user describing what was done (or what went wrong). Keep it under "
    "3 sentences unless the user asked for detail."
)


# Special "meta-tools" the model can call to signal clarification/refusal.
# DECISION: model uses these via function-calling rather than via free text
# because function-calling is more reliable for structured signals. The agent
# loop intercepts these meta-tools and treats them as control flow, not
# real tool calls.
_META_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "request_clarification",
            "description": (
                "Ask the user a clarifying question. Use when the request is "
                "ambiguous or missing required information."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The clarifying question to ask the user.",
                    }
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refuse_request",
            "description": (
                "Refuse the request because it is out of scope or unsafe. Use sparingly."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the request is being refused.",
                    }
                },
                "required": ["reason"],
            },
        },
    },
]


def _build_openai_tool_definitions(
    available_tools: list[str],
    tool_schemas: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build OpenAI function-calling tool definitions from available tools."""
    defs: list[dict[str, Any]] = list(_META_TOOLS)
    for tool_name in available_tools:
        schema = tool_schemas.get(tool_name, {"type": "object", "additionalProperties": True})
        defs.append(
            {
                "type": "function",
                "function": {
                    "name": _to_openai_name(tool_name),
                    "description": f"Tool: {tool_name}",
                    "parameters": schema,
                },
            }
        )
    return defs


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost. Returns 0 if pricing not known (don't fail closed)."""
    pricing = _OPENAI_PRICING_PER_MTOK.get(model)
    if pricing is None:
        return 0.0
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing[
        "output"
    ]


class OpenAIBackend(InferenceBackend):
    """OpenAI implementation of InferenceBackend.

    Reads `OPENAI_API_KEY` from env per ADR 0002 §6 (env-based auth) and
    ADR 0011 §B4 (backend fetches own env vars).

    Constructor takes `model_id` — the OpenAI model name (e.g., "gpt-4o-mini").
    Per ADR 0011 §1: one backend class per TRANSPORT, all OpenAI-served models
    go through this class configured with the right model_id.

    All chat-completion API calls are wrapped in `self._call_llm` for retry
    per ADR 0011 §D.
    """

    provider = "openai"
    cost_model = "per_token"

    # Approximate context windows (tokens). Advisory only — used for telemetry;
    # never consumed by agent branching. Update when OpenAI changes model specs.
    _MAX_CONTEXT_BY_MODEL = {
        "gpt-4o-mini": 128_000,
        "gpt-4o": 128_000,
    }

    def __init__(self, model_id: str = _DEFAULT_OPENAI_MODEL) -> None:
        super().__init__(model_id=model_id)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise BackendConfigError(
                backend="openai",
                missing="OPENAI_API_KEY",
                hint="Set OPENAI_API_KEY in the environment. See .env.example.",
            )
        # DECISION: import openai lazily so unit tests can run without the
        # library installed (we mock the client in tests).
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self.max_context = self._MAX_CONTEXT_BY_MODEL.get(model_id, 128_000)

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        context_block = json.dumps(request.context, default=str, indent=2)
        tool_definitions = _build_openai_tool_definitions(
            request.available_tools, request.tool_schemas
        )

        # DECISION: temperature=0 for planning. We want deterministic, structured
        # output. Variability in plans makes eval results noisy.
        async def _do_call() -> Any:
            return await self._client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {
                        "role": "system",
                        "content": _PLAN_SYSTEM_PROMPT.format(context_block=context_block),
                    },
                    {"role": "user", "content": request.user_input},
                ],
                # DECISION: cast to the OpenAI SDK's union type. Our dicts are
                # structurally valid ChatCompletionFunctionToolParam shapes, but
                # pyright can't see that through plain dict literals. Cast keeps
                # the helper function plain Python without forcing every call site
                # to import the SDK's TypedDicts.
                tools=cast("list[ChatCompletionToolUnionParam]", tool_definitions),
                tool_choice="auto",
                temperature=0,
            )

        response = await self._call_llm(_do_call, telemetry_kind="plan_task")

        message = response.choices[0].message
        # DECISION: openai-python now distinguishes function tool calls from
        # custom (non-function) tool calls in the response union. We only ever
        # send function tools, so filter to that variant. Anything else is a
        # protocol violation by the model — log and skip rather than crash.
        raw_tool_calls = message.tool_calls or []
        tool_calls: list[ChatCompletionMessageFunctionToolCall] = [
            tc for tc in raw_tool_calls if _is_function_tool_call(tc)
        ]

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = _estimate_cost_usd(self.model_id, input_tokens, output_tokens)

        # Empty tool_calls means model emitted only free text — treat as
        # intent_unclear if the text looks like a question, else refuse.
        if not tool_calls:
            return PlanResult(
                plan=None,
                intent_unclear=True,
                request_type=None,
                request_complexity=None,
                clarification_question=(
                    message.content or "Could you clarify what you'd like me to do?"
                ),
                refusal_reason=None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

        # Intercept meta-tools (clarification / refusal) before treating
        # remaining calls as real tools.
        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if fn_name == "request_clarification":
                return PlanResult(
                    plan=None,
                    intent_unclear=True,
                    request_type=None,
                    request_complexity=None,
                    clarification_question=args.get("question", "Could you clarify?"),
                    refusal_reason=None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                )
            if fn_name == "refuse_request":
                return PlanResult(
                    plan=None,
                    intent_unclear=False,
                    request_type=None,
                    request_complexity=None,
                    clarification_question=None,
                    refusal_reason=args.get("reason", "Request out of scope."),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                )

        # All remaining tool_calls are real tools — build the plan.
        plan: list[ToolCallStep] = []
        for tc in tool_calls:
            fn_name = tc.function.name
            if fn_name in {"request_clarification", "refuse_request"}:
                continue  # already handled above
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            internal_name = _from_openai_name(fn_name)
            plan.append(ToolCallStep(tool=internal_name, arguments=args))

        complexity = (
            RequestComplexity.SINGLE_TOOL if len(plan) == 1 else RequestComplexity.MULTI_TOOL
        )

        # DECISION: request_type inference is naive for v1 — infer from the
        # first tool's verb in the dotted name (create/update/delete/read/write).
        # v2 should let the model declare request_type explicitly.
        request_type = _infer_request_type_from_plan(plan)

        return PlanResult(
            plan=plan,
            intent_unclear=False,
            request_type=request_type,
            request_complexity=complexity,
            clarification_question=None,
            refusal_reason=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        # DECISION: higher temperature (0.3) for natural-language response.
        # Some variation is fine here; we want readable prose, not deterministic
        # text. Still low enough to avoid creative drift.
        async def _do_call() -> Any:
            return await self._client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": _INTERPRET_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Original request: {request.user_input}\n\n"
                            f"What happened:\n{request.action_log_summary}\n\n"
                            f"Respond to the user."
                        ),
                    },
                ],
                temperature=0.3,
            )

        response = await self._call_llm(_do_call, telemetry_kind="interpret_results")
        message = response.choices[0].message
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = _estimate_cost_usd(self.model_id, input_tokens, output_tokens)
        return InterpretResult(
            response_text=message.content or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


def _is_function_tool_call(
    tc: ChatCompletionMessageToolCallUnion,
) -> TypeGuard[ChatCompletionMessageFunctionToolCall]:
    """Narrow the SDK union to the function variant.

    Used before accessing `.function` on a tool call. Custom (non-function)
    tool calls have `.custom` instead and don't carry a name matching our
    function-calling convention — we filter them out at the call site.
    """
    return getattr(tc, "type", None) == "function" and hasattr(tc, "function")


def _infer_request_type_from_plan(plan: list[ToolCallStep]) -> RequestType:
    """Heuristic: infer request_type from the first tool's verb."""
    if not plan:
        return RequestType.VALIDATION
    first_tool = plan[0].tool  # e.g., "calendar.create_event"
    verb_match = re.search(r"\.(\w+)", first_tool)
    if not verb_match:
        return RequestType.VALIDATION
    verb = verb_match.group(1)
    if verb.startswith("create") or verb.startswith("send") or verb.startswith("write"):
        return RequestType.CREATION
    if verb.startswith("update") or verb.startswith("edit"):
        return RequestType.EDIT
    if verb.startswith("delete"):
        return RequestType.DELETE
    return RequestType.VALIDATION
