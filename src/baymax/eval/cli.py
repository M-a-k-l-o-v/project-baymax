"""Command-line entrypoints for BAYMAX eval runs."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

from baymax.eval.agent_runner import run_agent_scenarios
from baymax.eval.lora_runner import (
    LocalLoraAgent,
    LocalLoraConfig,
    LocalLoraDependencyError,
    run_lora_scenarios,
)
from baymax.eval.runner import ScenarioRunResult, ScriptedAgent, run_scenarios
from baymax.eval.scenario_loader import load_scenarios
from baymax.eval.scorer import AgentResponse
from baymax.service.inference import OpenAIBackend


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-scripted":
        _run_scripted(
            scenarios_dir=args.scenarios,
            responses_path=args.responses,
            output_path=args.output,
        )
        return 0

    if args.command == "run-agent-openai":
        asyncio.run(
            _run_agent_openai(
                scenarios_dir=args.scenarios,
                output_path=args.output,
                model=args.model,
            )
        )
        return 0

    if args.command == "run-agent-lora":
        _run_agent_local(
            scenarios_dir=args.scenarios,
            output_path=args.output,
            base_model=args.base_model,
            adapter_path=args.adapter,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            trust_remote_code=args.trust_remote_code,
            allow_cpu=args.allow_cpu,
            limit=args.limit,
            scenario_ids=args.scenario_id,
            runner="agent_lora",
            backend_name=f"local-lora:{args.base_model}",
        )
        return 0

    if args.command == "run-agent-local":
        _run_agent_local(
            scenarios_dir=args.scenarios,
            output_path=args.output,
            base_model=args.base_model,
            adapter_path=None,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            trust_remote_code=args.trust_remote_code,
            allow_cpu=args.allow_cpu,
            limit=args.limit,
            scenario_ids=args.scenario_id,
            runner="agent_local",
            backend_name=f"local-base:{args.base_model}",
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="baymax-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scripted_parser = subparsers.add_parser(
        "run-scripted",
        help="run scenarios with scripted agent responses",
    )
    scripted_parser.add_argument(
        "--scenarios",
        type=Path,
        required=True,
        help="directory containing scenario JSON files",
    )
    scripted_parser.add_argument(
        "--responses",
        type=Path,
        required=True,
        help="JSON file mapping scenario IDs to scripted responses",
    )
    scripted_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="path to write eval result JSON",
    )

    agent_openai_parser = subparsers.add_parser(
        "run-agent-openai",
        help="run scenarios with Marv's agent core and the OpenAI inference backend",
    )
    agent_openai_parser.add_argument(
        "--scenarios",
        type=Path,
        required=True,
        help="directory containing scenario JSON files",
    )
    agent_openai_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="path to write eval result JSON",
    )
    agent_openai_parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model name to use for the naive agent baseline",
    )

    agent_lora_parser = subparsers.add_parser(
        "run-agent-lora",
        help="run scenarios with a local Qwen LoRA adapter",
    )
    agent_lora_parser.add_argument(
        "--scenarios",
        type=Path,
        required=True,
        help="directory containing scenario JSON files",
    )
    agent_lora_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="path to write eval result JSON",
    )
    agent_lora_parser.add_argument(
        "--adapter",
        type=Path,
        required=True,
        help="LoRA adapter directory, e.g. models/qwen.../adapter",
    )
    agent_lora_parser.add_argument(
        "--base-model",
        default="Qwen/Qwen2.5-1.5B-Instruct",
        help="base model ID used with the LoRA adapter",
    )
    agent_lora_parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
        help="maximum generated tokens per scenario",
    )
    agent_lora_parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="generation temperature; 0 means deterministic greedy decoding",
    )
    agent_lora_parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="pass trust_remote_code=True when loading model/tokenizer",
    )
    agent_lora_parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="allow CPU inference when CUDA is unavailable",
    )
    agent_lora_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="optional scenario limit for quick local checks",
    )
    agent_lora_parser.add_argument(
        "--scenario-id",
        action="append",
        default=[],
        help="scenario ID to run; repeat for multiple IDs",
    )

    agent_local_parser = subparsers.add_parser(
        "run-agent-local",
        help="run scenarios with a local base model without a LoRA adapter",
    )
    agent_local_parser.add_argument(
        "--scenarios",
        type=Path,
        required=True,
        help="directory containing scenario JSON files",
    )
    agent_local_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="path to write eval result JSON",
    )
    agent_local_parser.add_argument(
        "--base-model",
        default="Qwen/Qwen2.5-1.5B-Instruct",
        help="base model ID to evaluate",
    )
    agent_local_parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
        help="maximum generated tokens per scenario",
    )
    agent_local_parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="generation temperature; 0 means deterministic greedy decoding",
    )
    agent_local_parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="pass trust_remote_code=True when loading model/tokenizer",
    )
    agent_local_parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="allow CPU inference when CUDA is unavailable",
    )
    agent_local_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="optional scenario limit for quick local checks",
    )
    agent_local_parser.add_argument(
        "--scenario-id",
        action="append",
        default=[],
        help="scenario ID to run; repeat for multiple IDs",
    )

    return parser


def _run_scripted(
    *,
    scenarios_dir: Path,
    responses_path: Path,
    output_path: Path,
) -> None:
    run_id = str(uuid4())
    scenarios = load_scenarios(scenarios_dir)
    responses = load_scripted_responses(responses_path)
    results = run_scenarios(
        scenarios,
        ScriptedAgent(responses=responses),
        run_id=run_id,
    )
    output = build_result_payload(
        results=results,
        backend_name="scripted",
        run_id=run_id,
        runner="scripted",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True),
        encoding="utf-8",
    )


async def _run_agent_openai(
    *,
    scenarios_dir: Path,
    output_path: Path,
    model: str,
) -> None:
    run_id = str(uuid4())
    scenarios = load_scenarios(scenarios_dir)
    results = await run_agent_scenarios(
        scenarios=scenarios,
        inference=OpenAIBackend(model=model),
        run_id=run_id,
    )
    output = build_result_payload(
        results=results,
        backend_name=f"openai:{model}",
        run_id=run_id,
        runner="agent_openai",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _run_agent_local(
    *,
    scenarios_dir: Path,
    output_path: Path,
    base_model: str,
    adapter_path: Path | None,
    max_new_tokens: int,
    temperature: float,
    trust_remote_code: bool,
    allow_cpu: bool,
    limit: int | None,
    scenario_ids: list[str],
    runner: str,
    backend_name: str,
) -> None:
    run_id = str(uuid4())
    scenarios = load_scenarios(scenarios_dir)
    if scenario_ids:
        selected_ids = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.id in selected_ids]
        missing_ids = sorted(selected_ids - {scenario.id for scenario in scenarios})
        if missing_ids:
            raise SystemExit(f"error: unknown scenario IDs: {', '.join(missing_ids)}")
    if limit is not None:
        scenarios = scenarios[:limit]

    try:
        agent = LocalLoraAgent(
            LocalLoraConfig(
                base_model=base_model,
                adapter_path=adapter_path,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                trust_remote_code=trust_remote_code,
                allow_cpu=allow_cpu,
            )
        )
    except (LocalLoraDependencyError, FileNotFoundError, RuntimeError) as error:
        raise SystemExit(f"error: {error}") from error

    results = run_lora_scenarios(
        scenarios=scenarios,
        agent=agent,
        run_id=run_id,
    )
    output = build_result_payload(
        results=results,
        backend_name=backend_name,
        run_id=run_id,
        runner=runner,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_scripted_responses(path: Path) -> dict[str, AgentResponse]:
    with path.open(encoding="utf-8") as responses_file:
        raw_responses = json.load(responses_file)

    if not isinstance(raw_responses, dict):
        raise ValueError("scripted responses file must contain a JSON object")

    return {
        scenario_id: AgentResponse.model_validate(response)
        for scenario_id, response in raw_responses.items()
    }


def build_result_payload(
    *,
    results: list[ScenarioRunResult],
    backend_name: str,
    run_id: str | None = None,
    runner: str = "scripted",
) -> dict[str, Any]:
    result_run_id = run_id or str(uuid4())
    return {
        "run_id": result_run_id,
        "backend_name": backend_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "scenario_count": len(results),
        "aggregate_metrics": _aggregate_metrics(results),
        "scenario_results": [
            {
                "scenario_id": result.scenario_id,
                "trace_id": result.trace_id,
                "task_id": result.task_id,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
                "raw_model_output": result.raw_model_output,
                "agent_response": (
                    result.agent_response.model_dump(mode="json")
                    if result.agent_response is not None
                    else None
                ),
                "score": result.score.model_dump(mode="json"),
                "tool_results": [
                    tool_result.model_dump(mode="json") for tool_result in result.tool_results
                ],
                "final_state": result.final_state,
            }
            for result in results
        ],
        "benchmark_config": {
            "runner": runner,
            "uses_fake_adapters": True,
        },
    }


def _aggregate_metrics(results: list[ScenarioRunResult]) -> dict[str, float | int | None]:
    scenario_count = len(results)
    if scenario_count == 0:
        return {
            "task_success_rate": None,
            "average_tool_call_accuracy": None,
            "average_argument_accuracy": None,
            "average_clarification_accuracy": None,
            "average_refusal_accuracy": None,
            "average_hallucination_rate": None,
            "average_latency_ms": None,
            "total_cost_usd": 0.0,
        }

    clarification_scores = [
        result.score.clarification_accuracy
        for result in results
        if result.score.clarification_accuracy is not None
    ]
    refusal_scores = [
        result.score.refusal_accuracy
        for result in results
        if result.score.refusal_accuracy is not None
    ]

    return {
        "task_success_rate": sum(result.score.task_success for result in results) / scenario_count,
        "average_tool_call_accuracy": _mean(
            [result.score.tool_call_accuracy for result in results]
        ),
        "average_argument_accuracy": _mean([result.score.argument_accuracy for result in results]),
        "average_clarification_accuracy": _mean(clarification_scores),
        "average_refusal_accuracy": _mean(refusal_scores),
        "average_hallucination_rate": _mean(
            [result.score.hallucination_rate for result in results]
        ),
        "average_latency_ms": _mean([result.latency_ms for result in results]),
        "total_cost_usd": sum(result.cost_usd for result in results),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


if __name__ == "__main__":
    raise SystemExit(main())
