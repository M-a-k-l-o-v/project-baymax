"""Summarize manual review labels for an external dataset sample."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from baymax.models.external_review import (
    DEFAULT_REJECTION_THRESHOLD,
    ExternalReviewSample,
    summarize_external_review_sample,
)

DEFAULT_INPUT_PATH = Path("data/sft/v1/xlam-review-sample.json")
DEFAULT_OUTPUT_PATH = Path("data/sft/v1/xlam-review-summary.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to a filled manual review sample JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write the review summary JSON.",
    )
    parser.add_argument(
        "--rejection-threshold",
        type=float,
        default=DEFAULT_REJECTION_THRESHOLD,
        help="Reject the dataset if reviewed error rate is greater than this value.",
    )
    args = parser.parse_args()

    try:
        sample = ExternalReviewSample.model_validate_json(args.input.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: review sample not found: {args.input}", file=sys.stderr)
        return 1
    except ValidationError as error:
        print(f"error: invalid review sample: {error}", file=sys.stderr)
        return 1

    summary = summarize_external_review_sample(
        sample,
        rejection_threshold=args.rejection_threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")

    print(f"Wrote review summary to {args.output}")
    print(
        "Reviewed "
        f"{summary.reviewed_rows}/{summary.total_rows} rows; "
        f"error_rate={summary.error_rate if summary.error_rate is not None else 'n/a'}"
    )
    if summary.reject_dataset is None:
        print("Decision: incomplete review")
    elif summary.reject_dataset:
        print("Decision: reject dataset")
    else:
        print("Decision: keep dataset")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
