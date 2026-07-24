import json
from pathlib import Path

from baymax.eval.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"


def test_run_scripted_cli_writes_result_json(tmp_path: Path) -> None:
    responses_path = tmp_path / "scripted_responses.json"
    output_path = tmp_path / "v1-baseline.json"
    responses_path.write_text(
        json.dumps(
            {
                "calendar_clarify_time_001": {
                    "message": "What time should I schedule it?",
                    "tool_calls": [],
                }
            }
        ),
        encoding="utf-8",
    )
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    source_scenario = SCENARIO_DIR / "calendar_clarify_time_001.json"
    (scenarios_dir / source_scenario.name).write_text(
        source_scenario.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run-scripted",
            "--scenarios",
            str(scenarios_dir),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ]
    )

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["backend_name"] == "scripted"
    assert result["scenario_count"] == 1
    assert result["aggregate_metrics"]["task_success_rate"] == 1.0
    assert result["scenario_results"][0]["scenario_id"] == "calendar_clarify_time_001"
    assert result["scenario_results"][0]["trace_id"] is None
    assert result["scenario_results"][0]["task_id"].endswith(".calendar_clarify_time_001.0")
    assert result["scenario_results"][0]["latency_ms"] >= 0
    assert result["scenario_results"][0]["cost_usd"] == 0.0
    assert result["scenario_results"][0]["score"]["task_success"] is True
    assert result["aggregate_metrics"]["average_latency_ms"] >= 0
    assert result["aggregate_metrics"]["total_cost_usd"] == 0.0
    assert result["benchmark_config"] == {
        "runner": "scripted",
        "uses_fake_adapters": True,
    }


def test_run_scripted_cli_creates_output_parent_directory(tmp_path: Path) -> None:
    responses_path = tmp_path / "scripted_responses.json"
    output_path = tmp_path / "nested" / "results" / "v1-baseline.json"
    responses_path.write_text("{}", encoding="utf-8")
    scenarios_dir = tmp_path / "empty_scenarios"
    scenarios_dir.mkdir()

    exit_code = main(
        [
            "run-scripted",
            "--scenarios",
            str(scenarios_dir),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ]
    )

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert output_path.exists()
    assert result["scenario_count"] == 0
    assert result["aggregate_metrics"]["task_success_rate"] is None
    assert result["aggregate_metrics"]["average_latency_ms"] is None
    assert result["aggregate_metrics"]["total_cost_usd"] == 0.0
