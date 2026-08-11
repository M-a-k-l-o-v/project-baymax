"""Validate a Phase 2 SFT training config and its reproducibility hash."""

from __future__ import annotations

import argparse
from pathlib import Path

from baymax.models.training_config import (
    load_training_config,
    training_config_with_hash,
    validate_training_config,
    write_training_config,
)

DEFAULT_CONFIG_PATH = Path("configs/sft/qwen2_5_1_5b_lora_v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Training config JSON path.",
    )
    parser.add_argument(
        "--check-paths",
        action="store_true",
        help="Verify referenced local dataset and eval paths exist.",
    )
    parser.add_argument(
        "--write-hash",
        action="store_true",
        help="Update config_hash in the config file before validating.",
    )
    args = parser.parse_args()

    if args.write_hash:
        config = training_config_with_hash(load_training_config(args.config))
        write_training_config(args.config, config)

    report = validate_training_config(args.config, check_paths=args.check_paths)

    print(f"Valid: {report.valid}")
    print(f"Config hash: {report.config_hash}")
    print(f"Expected hash: {report.expected_config_hash}")
    if report.issues:
        print(f"Issues: {len(report.issues)}")
        for issue in report.issues:
            print(f"- {issue.location}: {issue.message}")

    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
