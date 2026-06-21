"""Inference service — abstracts the LLM backend behind a uniform interface.

Per ADR 0005 (inference backend swappable abstraction).

v1: OpenAI backend (gpt-4o-mini default — cheap, supports tool calling well).
v2: Anthropic and local-MLX backends.

The agent core calls `InferenceBackend.plan_task()` and `interpret_results()`
— same interface regardless of backend.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from baymax.core.contracts import (
    RequestComplexity,
    RequestType,
    ToolCallStep,
)

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
    """Swappable LLM backend. v1 implementation: OpenAI. v2: Anthropic, MLX."""

    @abstractmethod
    async def plan_task(self, request: PlanRequest) -> PlanResult:
        """Construct a tool-call plan from user input + available tools."""

    @abstractmethod
    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        """Convert raw tool outputs into a user-facing response message."""


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

    Reads `OPENAI_API_KEY` from env per ADR 0002 §6 (env-based auth).
    Caller may pass a different model name via constructor.
    """

    def __init__(self, model: str = _DEFAULT_OPENAI_MODEL) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment. See .env.example.")
        # DECISION: import openai lazily so unit tests can run without the
        # library installed (we mock the client in tests).
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        context_block = json.dumps(request.context, default=str, indent=2)
        tool_definitions = _build_openai_tool_definitions(
            request.available_tools, request.tool_schemas
        )

        # DECISION: temperature=0 for planning. We want deterministic, structured
        # output. Variability in plans makes eval results noisy.
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": _PLAN_SYSTEM_PROMPT.format(context_block=context_block),
                },
                {"role": "user", "content": request.user_input},
            ],
            tools=tool_definitions,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = _estimate_cost_usd(self._model, input_tokens, output_tokens)

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
        response = await self._client.chat.completions.create(
            model=self._model,
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

        message = response.choices[0].message
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = _estimate_cost_usd(self._model, input_tokens, output_tokens)
        return InterpretResult(
            response_text=message.content or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


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
