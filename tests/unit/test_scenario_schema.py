import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios" / "v1"
SCHEMA_PATH = REPO_ROOT / "src" / "baymax" / "eval" / "schemas" / "scenario.schema.json"


def test_all_v1_scenarios_validate_against_committed_json_schema() -> None:
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    scenario_paths = sorted(SCENARIO_DIR.glob("*.json"))

    assert scenario_paths, "Expected at least one v1 scenario fixture"

    failures: list[str] = []
    for path in scenario_paths:
        with path.open(encoding="utf-8") as scenario_file:
            scenario = json.load(scenario_file)

        errors = sorted(validator.iter_errors(scenario), key=lambda error: error.path)
        failures.extend(f"{path}: {error.message}" for error in errors)

    assert failures == []
