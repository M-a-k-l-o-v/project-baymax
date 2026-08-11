"""Run a local Qwen model, optionally with a LoRA adapter, against eval scenarios."""

from __future__ import annotations

import json
import re
from importlib import import_module
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from baymax.eval.agent_runner import FAKE_TOOL_SCHEMAS
from baymax.eval.fake_executor import execute_tool_calls
from baymax.eval.runner import ScenarioRunResult
from baymax.eval.scenario_loader import Scenario
from baymax.eval.scorer import AgentResponse, AgentToolCall, score_response
from baymax.models.sft_dataset import DEFAULT_SFT_SYSTEM_PROMPT


class LocalLoraDependencyError(RuntimeError):
    """Raised when optional local-inference dependencies are unavailable."""


class LocalLoraConfig(BaseModel):
    """Configuration for loading a local model, optionally with a LoRA adapter."""

    model_config = ConfigDict(extra="forbid")

    base_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    adapter_path: Path | None = None
    max_new_tokens: int = Field(default=256, ge=1)
    temperature: float = Field(default=0.0, ge=0)
    trust_remote_code: bool = False
    allow_cpu: bool = False


class LocalLoraInvocation(BaseModel):
    """One raw local-model invocation converted to the eval boundary."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str
    response: AgentResponse


class LocalLoraAgentLike(Protocol):
    def invoke(self, scenario: Scenario) -> LocalLoraInvocation:
        """Return one parsed local-model response for a scenario."""
        ...


class LocalLoraAgent:
    """Local Qwen wrapper for eval runs, with optional LoRA adapter."""

    def __init__(self, config: LocalLoraConfig) -> None:
        dependencies = _load_local_lora_dependencies(include_peft=config.adapter_path is not None)
        self._torch = dependencies["torch"]
        self._transformers = dependencies["transformers"]
        self._config = config

        if config.adapter_path is not None and not config.adapter_path.exists():
            raise FileNotFoundError(f"adapter path does not exist: {config.adapter_path}")

        if not self._torch.cuda.is_available() and not config.allow_cpu:
            raise RuntimeError(
                "CUDA is not available. Use --allow-cpu for a slow CPU eval run, "
                "or run on a CUDA GPU machine."
            )

        self._tokenizer = self._transformers.AutoTokenizer.from_pretrained(
            config.base_model,
            trust_remote_code=config.trust_remote_code,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        model_kwargs: dict[str, Any] = {"trust_remote_code": config.trust_remote_code}
        if self._torch.cuda.is_available():
            model_kwargs["device_map"] = "auto"
            model_kwargs["torch_dtype"] = (
                self._torch.bfloat16
                if self._torch.cuda.is_bf16_supported()
                else self._torch.float16
            )

        model = self._transformers.AutoModelForCausalLM.from_pretrained(
            config.base_model,
            **model_kwargs,
        )
        if config.adapter_path is not None:
            peft = dependencies["peft"]
            model = peft.PeftModel.from_pretrained(model, config.adapter_path)

        self._model = model
        self._model.eval()

    def invoke(self, scenario: Scenario) -> LocalLoraInvocation:
        messages = build_lora_scenario_messages(scenario)
        prompt = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        tokenized = self._tokenizer(prompt, return_tensors="pt")
        device = next(self._model.parameters()).device
        tokenized = {key: value.to(device) for key, value in tokenized.items()}

        generation_kwargs: dict[str, Any] = {
            **tokenized,
            "max_new_tokens": self._config.max_new_tokens,
            "pad_token_id": self._tokenizer.eos_token_id,
            "do_sample": self._config.temperature > 0,
        }
        if self._config.temperature > 0:
            generation_kwargs["temperature"] = self._config.temperature

        with self._torch.no_grad():
            output_ids = self._model.generate(**generation_kwargs)

        generated_ids = output_ids[0][tokenized["input_ids"].shape[-1] :]
        raw_text = self._tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        return LocalLoraInvocation(
            raw_text=raw_text,
            response=parse_lora_agent_response(raw_text),
        )


def run_lora_scenario(
    scenario: Scenario,
    agent: LocalLoraAgentLike,
    *,
    run_id: str | None = None,
) -> ScenarioRunResult:
    """Run one scenario through a local LoRA agent and score it."""

    started_at = perf_counter()
    invocation = agent.invoke(scenario)
    execution = execute_tool_calls(
        initial_state=scenario.initial_state,
        tool_calls=invocation.response.tool_calls,
    )
    score = score_response(scenario, invocation.response)
    latency_ms = int((perf_counter() - started_at) * 1000)

    return ScenarioRunResult(
        scenario_id=scenario.id,
        task_id=f"{run_id}.{scenario.id}.0" if run_id else None,
        latency_ms=latency_ms,
        raw_model_output=invocation.raw_text,
        agent_response=invocation.response,
        score=score,
        tool_results=execution.tool_results,
        final_state=execution.final_state,
    )


def run_lora_scenarios(
    scenarios: list[Scenario],
    agent: LocalLoraAgentLike,
    *,
    run_id: str | None = None,
) -> list[ScenarioRunResult]:
    """Run multiple scenarios through a local LoRA agent."""

    return [run_lora_scenario(scenario, agent, run_id=run_id) for scenario in scenarios]


def build_lora_scenario_messages(scenario: Scenario) -> list[dict[str, str]]:
    """Build chat messages matching the SFT prompt style."""

    return [
        {"role": "system", "content": DEFAULT_SFT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "Available tools:",
                    json.dumps(_available_tool_specs(scenario), sort_keys=True),
                    "",
                    "User request:",
                    json.dumps(
                        {
                            "current_time": scenario.current_time.isoformat(),
                            "initial_state": scenario.initial_state,
                            "request": scenario.user_input,
                        },
                        sort_keys=True,
                    ),
                ]
            ),
        },
    ]


def parse_lora_agent_response(raw_text: str) -> AgentResponse:
    """Parse xLAM-style local model text into the BAYMAX eval boundary."""

    candidate = _extract_json_candidate(raw_text)
    if candidate is None:
        return AgentResponse(message=raw_text or None)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return AgentResponse(message=raw_text or None)

    if isinstance(parsed, dict) and ("tool_calls" in parsed or "message" in parsed):
        return _parse_agent_response_dict(parsed, fallback_message=raw_text)

    values = _tool_call_values_from_parsed(parsed)
    tool_calls: list[AgentToolCall] = []
    message: str | None = None
    for value in values:
        parsed_call = _parse_tool_call(value)
        if parsed_call is None:
            continue

        tool_name, arguments = parsed_call
        if tool_name == "request_clarification":
            message = _string_argument(arguments, "question") or raw_text or None
            continue
        if tool_name == "refuse_request":
            message = _string_argument(arguments, "reason") or raw_text or None
            continue

        try:
            tool_calls.append(AgentToolCall(tool=tool_name, arguments=arguments))
        except ValueError:
            continue

    return AgentResponse(tool_calls=tool_calls, message=message)


def _parse_agent_response_dict(
    parsed: dict[str, Any],
    *,
    fallback_message: str,
) -> AgentResponse:
    raw_tool_calls = parsed.get("tool_calls", [])
    values = raw_tool_calls if isinstance(raw_tool_calls, list) else []
    tool_calls: list[AgentToolCall] = []
    for value in values:
        parsed_call = _parse_tool_call(value)
        if parsed_call is None:
            continue
        tool_name, arguments = parsed_call
        try:
            tool_calls.append(AgentToolCall(tool=tool_name, arguments=arguments))
        except ValueError:
            continue

    message = parsed.get("message")
    return AgentResponse(
        tool_calls=tool_calls,
        message=message if isinstance(message, str) else fallback_message or None,
    )


def _available_tool_specs(scenario: Scenario) -> list[dict[str, Any]]:
    tool_specs = [
        {
            "name": "request_clarification",
            "description": "Ask a clarification question when required information is missing.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
        {
            "name": "refuse_request",
            "description": "Refuse when the request is unsupported or out of scope.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    ]
    for tool in scenario.available_tools:
        tool_specs.append(
            {
                "name": tool,
                "description": f"Tool: {tool}",
                "parameters": FAKE_TOOL_SCHEMAS.get(
                    tool,
                    {"type": "object", "additionalProperties": True},
                ),
            }
        )

    return tool_specs


def _parse_tool_call(value: Any) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(value, dict):
        return None

    function = value.get("function")
    if isinstance(function, dict):
        tool_name = function.get("name")
        arguments = function.get("arguments", {})
    else:
        tool_name = value.get("name") or value.get("tool") or value.get("tool_name")
        arguments = value.get("arguments", value.get("parameters", value.get("params", {})))

    if not isinstance(tool_name, str):
        return None

    return tool_name, _parse_arguments(arguments)


def _tool_call_values_from_parsed(parsed: Any) -> list[Any]:
    if not isinstance(parsed, list):
        return [parsed]

    if _is_alternating_tool_call_list(parsed):
        return [
            {"name": parsed[index], "arguments": parsed[index + 1]}
            for index in range(0, len(parsed), 2)
        ]

    return parsed


def _is_alternating_tool_call_list(values: list[Any]) -> bool:
    if len(values) == 0 or len(values) % 2 != 0:
        return False

    return all(
        isinstance(values[index], str) and isinstance(values[index + 1], dict)
        for index in range(0, len(values), 2)
    )


def _parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    return {}


def _string_argument(arguments: dict[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    return value if isinstance(value, str) else None


def _extract_json_candidate(raw_text: str) -> str | None:
    stripped = raw_text.strip()
    if not stripped:
        return None

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        stripped = fenced_match.group(1).strip()

    for start_index, character in enumerate(stripped):
        if character in "[{":
            candidate = _balanced_json_slice(stripped[start_index:])
            if candidate is not None:
                return candidate

    return None


def _balanced_json_slice(value: str) -> str | None:
    opening = value[0]
    closing = "]" if opening == "[" else "}"
    depth = 0
    in_string = False
    escaped = False

    for index, character in enumerate(value):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return value[: index + 1]

    return None


def _load_local_lora_dependencies(*, include_peft: bool) -> dict[str, Any]:
    try:
        torch = import_module("torch")
        transformers = import_module("transformers")
        peft = import_module("peft") if include_peft else None
    except ImportError as error:
        raise LocalLoraDependencyError(
            "Missing local inference dependencies. Install them with: "
            "python -m pip install torch transformers peft accelerate"
        ) from error

    dependencies = {
        "torch": torch,
        "transformers": transformers,
    }
    if peft is not None:
        dependencies["peft"] = peft

    return dependencies
