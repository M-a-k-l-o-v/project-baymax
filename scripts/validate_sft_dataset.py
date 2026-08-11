"""Validate generated Phase 2 SFT dataset files."""

from __future__ import annotations

import argparse
from pathlib import Path

from baymax.models.sft_validation import validate_sft_dataset

DEFAULT_DATASET_DIR = Path("data/sft/v1/xlam")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=(
            "Directory containing train.jsonl, validation.jsonl, test.jsonl, "
            "and split-manifest.json."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional path for the validation report. Defaults to "
            "<dataset-dir>/validation-report.json."
        ),
    )
    args = parser.parse_args()

    report = validate_sft_dataset(args.dataset_dir)
    output_path = args.output or args.dataset_dir / "validation-report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    print(f"Wrote validation report to {output_path}")
    print(f"Valid: {report.valid}")
    if report.converted_rows is not None:
        print(
            "Counts: "
            f"converted={report.converted_rows}, "
            f"train={report.splits['train'].actual_count}, "
            f"validation={report.splits['validation'].actual_count}, "
            f"test={report.splits['test'].actual_count}, "
            f"skipped={report.skipped_row_count}"
        )
    if report.issues:
        print(f"Top-level issues: {len(report.issues)}")

    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
