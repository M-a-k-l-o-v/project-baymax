"""MLX backend — local Apple-Silicon inference for Qwen (+ LoRA adapter).

Per ADR 0011 (§1 template per transport, §4 warmup, §7 registry coupling).

Key design points:
- Reads model metadata from `models/models.json` at construction (registry-driven per §7).
- Refuses to load an entry with `mlx_compatible: false` — MLX conversion of PEFT
  adapters is an ADR 0012 §Open item; when Ronin's pipeline emits MLX-compatible
  artifacts, that field flips.
- NO retry, ever (§D3): all MLX errors are deterministic. Any error raises
  `BackendError` directly.
- Warmup runs a real inference on `warmup_scenario.json` — forces Metal kernel
  compilation for the tool-calling generation path per §C1.
- Lazy `mlx` import so unit tests without MLX installed still pass.

Prompt format: uses Qwen 2.5 chat template with tools inlined as an
xLAM-style system-prompt instruction (matches Ronin's training data format).
Model output is parsed for JSON tool calls; the parsing lives here for now
but will move to a dedicated output adapter (`src/baymax/service/adapter.py`)
in a follow-up once xLAM → BAYMAX namespace translation grows non-trivial.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from baymax.core.contracts import (
    RequestComplexity,
    RequestType,
    ToolCallStep,
)
from baymax.core.exceptions import (
    BackendConfigError,
    BackendError,
    WarmupFailure,
)
from baymax.core.registry import load_registry_entry
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
)

# Warmup scenario location — matches the file written per ADR 0011 §C1.
_WARMUP_SCENARIO_PATH = Path(__file__).parent / "warmup" / "warmup_scenario.json"


class MLXBackend(InferenceBackend):
    """Local MLX inference for Qwen models with optional LoRA adapters.

    Constructor requires a `model_id` that resolves in the registry
    (`models/models.json`). If the entry has `mlx_compatible: false`,
    construction fails loud (ADR 0012 conversion plan not yet locked
    with Ronin).
    """

    provider = "mlx"
    cost_model = "amortized"
    max_context = 32_768  # Qwen 2.5 default; refined at load time if metadata says otherwise.

    def __init__(self, model_id: str) -> None:
        super().__init__(model_id=model_id)

        entry = load_registry_entry(model_id)
        if not entry.mlx_compatible:
            raise BackendConfigError(
                backend="mlx",
                missing=f"mlx_compatible=true for model {model_id!r}",
                hint=(
                    "The registered entry has mlx_compatible=false — Ronin's "
                    "PEFT adapter has not been converted to MLX format yet. "
                    "See ADR 0012 §Open items #4 (MLX conversion plan)."
                ),
            )

        # Lazy MLX import per §F: keeps unit tests portable to non-Mac CI.
        try:
            from mlx_lm import generate, load  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BackendConfigError(
                backend="mlx",
                missing="mlx-lm package",
                hint=(
                    "MLX runs on Apple Silicon only. Install with "
                    "`uv add mlx-lm` on a Mac; skip MLX integration tests "
                    "elsewhere by omitting HAVE_MLX=1."
                ),
            ) from exc

        self._generate = generate
        self._entry = entry

        # Adapter path resolved relative to repo root.
        weights_path = entry.mlx_artifact_path or entry.adapter_path
        if weights_path is None:
            raise BackendConfigError(
                backend="mlx",
                missing="mlx_artifact_path or adapter_path in registry entry",
                hint=f"Neither field set on entry {model_id!r}.",
            )
        try:
            self._model, self._tokenizer = load(weights_path)
        except FileNotFoundError as exc:
            raise BackendConfigError(
                backend="mlx",
                missing=f"weights at {weights_path}",
                hint=(
                    f"Registry says entry {model_id!r} weights are at {weights_path}, "
                    "but that path does not exist. Check that the checkpoint has been "
                    "downloaded / trained and the path is correct."
                ),
            ) from exc

    # ------------------------------------------------------------------
    # Warmup — real inference on a canned scenario per ADR 0011 §C.
    # ------------------------------------------------------------------

    async def warmup(self) -> None:
        try:
            scenario = json.loads(_WARMUP_SCENARIO_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WarmupFailure(
                stage="load_warmup_scenario",
                cause=f"Missing {_WARMUP_SCENARIO_PATH}",
                hint="This file ships with the codebase — check your working tree.",
            ) from exc
        except json.JSONDecodeError as exc:
            raise WarmupFailure(
                stage="load_warmup_scenario",
                cause=f"Malformed JSON in {_WARMUP_SCENARIO_PATH}: {exc}",
            ) from exc

        request = PlanRequest(
            user_input=scenario["user_input"],
            available_tools=scenario["available_tools"],
            context={"warmup": True, "current_time": scenario.get("current_time")},
            tool_schemas={},  # warmup scenario intentionally minimal
        )
        try:
            await self.plan_task(request)
        except BackendError as exc:
            # Backend-level failure DURING warmup = warmup failure. Reraise
            # as WarmupFailure so lifespan handling knows to exit rather
            # than pass it up as a request-time BackendError.
            raise WarmupFailure(
                stage="generate",
                cause=f"MLX inference on warmup scenario failed: {exc.kind}",
                hint=str(exc),
            ) from exc

    # ------------------------------------------------------------------
    # Core methods.
    # ------------------------------------------------------------------

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        prompt = _build_plan_prompt(request)
        try:
            raw_output = self._generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=512,
                verbose=False,
            )
        except BaseException as exc:  # noqa: BLE001 — deterministic; wrap and re-raise per §D3
            raise BackendError(
                kind="non_retriable",
                message=f"MLX generate failed for {self.model_id}: {exc}",
                underlying=exc,
                backend=self.provider,
            ) from exc

        plan, intent_unclear, clarification, refusal = _parse_plan_output(raw_output)

        complexity = None
        if plan:
            complexity = (
                RequestComplexity.SINGLE_TOOL if len(plan) == 1 else RequestComplexity.MULTI_TOOL
            )

        return PlanResult(
            plan=plan,
            intent_unclear=intent_unclear,
            request_type=_infer_request_type(plan) if plan else None,
            request_complexity=complexity,
            clarification_question=clarification,
            refusal_reason=refusal,
            # Token counts + cost: MLX has no per-token cost (amortized).
            # Token counts approximated from output length.
            input_tokens=0,
            output_tokens=len(raw_output.split()),
            cost_usd=0.0,
        )

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        prompt = _build_interpret_prompt(request)
        try:
            raw_output = self._generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=256,
                verbose=False,
            )
        except BaseException as exc:  # noqa: BLE001
            raise BackendError(
                kind="non_retriable",
                message=f"MLX generate failed for {self.model_id}: {exc}",
                underlying=exc,
                backend=self.provider,
            ) from exc

        return InterpretResult(
            response_text=raw_output.strip(),
            input_tokens=0,
            output_tokens=len(raw_output.split()),
            cost_usd=0.0,
        )


# ---------------------------------------------------------------------------
# Prompt building + output parsing (lightweight adapter — will split out to
# `src/baymax/service/adapter.py` when it grows non-trivial).
# ---------------------------------------------------------------------------


def _build_plan_prompt(request: PlanRequest) -> str:
    """Qwen-chat-style prompt with tools inlined (xLAM format)."""
    tools_block = "\n".join(f"- {t}" for t in request.available_tools)
    return (
        "<|im_start|>system\n"
        "You are BAYMAX, a personal-task agent. You have access to the tools listed.\n"
        "Emit tool calls as a JSON array: "
        '[{"name": "tool.name", "arguments": {...}}]. '
        "Use only the listed tools. If the request is ambiguous, emit "
        '[{"name": "request_clarification", "arguments": {"question": "..."}}]. '
        "If out of scope, emit "
        '[{"name": "refuse_request", "arguments": {"reason": "..."}}].\n\n'
        f"Available tools:\n{tools_block}\n\n"
        f"Context: {json.dumps(request.context, default=str)}\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"{request.user_input}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def _build_interpret_prompt(request: InterpretRequest) -> str:
    return (
        "<|im_start|>system\n"
        "You are BAYMAX. Given the user's request and a log of tool calls "
        "that were executed, write a concise natural-language response "
        "(under 3 sentences unless the user asked for detail).\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"Original request: {request.user_input}\n\n"
        f"What happened:\n{request.action_log_summary}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


_JSON_ARRAY_RE = re.compile(r"\[\s*\{.*?\}\s*\]", re.DOTALL)


def _parse_plan_output(
    raw: str,
) -> tuple[list[ToolCallStep] | None, bool, str | None, str | None]:
    """Extract tool calls from raw model output.

    Returns `(plan, intent_unclear, clarification_question, refusal_reason)`.
    Matches OpenAIBackend's semantics for the meta-tools so the agent code
    stays backend-uniform.
    """
    match = _JSON_ARRAY_RE.search(raw)
    if not match:
        # No JSON found — treat as clarification pending with the raw text.
        return None, True, raw.strip() or "Could you clarify what you'd like me to do?", None

    try:
        calls = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, True, "Could you clarify what you'd like me to do?", None

    if not isinstance(calls, list) or not calls:
        return None, True, "Could you clarify what you'd like me to do?", None

    # Handle meta-tools first (matches OpenAIBackend behaviour).
    for call in calls:
        name = call.get("name")
        args = call.get("arguments", {}) or {}
        if name == "request_clarification":
            return None, True, args.get("question", "Could you clarify?"), None
        if name == "refuse_request":
            return None, False, None, args.get("reason", "Request out of scope.")

    # Real tool calls.
    plan = [
        ToolCallStep(tool=call["name"], arguments=call.get("arguments", {}) or {})
        for call in calls
        if isinstance(call, dict) and "name" in call
    ]
    if not plan:
        return None, True, "Could you clarify?", None
    return plan, False, None, None


def _infer_request_type(plan: list[ToolCallStep]) -> RequestType:
    """Heuristic — mirror of OpenAIBackend's inference for uniformity."""
    if not plan:
        return RequestType.VALIDATION
    first_tool = plan[0].tool
    match = re.search(r"\.(\w+)", first_tool)
    if not match:
        return RequestType.VALIDATION
    verb = match.group(1)
    if verb.startswith(("create", "send", "write")):
        return RequestType.CREATION
    if verb.startswith(("update", "edit")):
        return RequestType.EDIT
    if verb.startswith("delete"):
        return RequestType.DELETE
    return RequestType.VALIDATION


# Silence "unused" lint for symbols kept for import consumers.
_ = Any
