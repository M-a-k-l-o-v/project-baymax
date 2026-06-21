"""Command-line entrypoints for BAYMAX eval runs."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

from baymax.eval.runner import ScenarioRunResult, ScriptedAgent, run_scenarios
from baymax.eval.scenario_loader import load_scenarios
from baymax.eval.scorer import AgentResponse


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

    return parser


def _run_scripted(
    *,
    scenarios_dir: Path,
    responses_path: Path,
    output_path: Path,
) -> None:
    scenarios = load_scenarios(scenarios_dir)
    responses = load_scripted_responses(responses_path)
    results = run_scenarios(scenarios, ScriptedAgent(responses=responses))
    output = build_result_payload(results=results, backend_name="scripted")

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
) -> dict[str, Any]:
    return {
        "run_id": str(uuid4()),
        "backend_name": backend_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "scenario_count": len(results),
        "aggregate_metrics": _aggregate_metrics(results),
        "scenario_results": [
            {
                "scenario_id": result.scenario_id,
                "score": result.score.model_dump(mode="json"),
                "tool_results": [
                    tool_result.model_dump(mode="json") for tool_result in result.tool_results
                ],
                "final_state": result.final_state,
            }
            for result in results
        ],
        "benchmark_config": {
            "runner": "scripted",
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
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


if __name__ == "__main__":
    raise SystemExit(main())
