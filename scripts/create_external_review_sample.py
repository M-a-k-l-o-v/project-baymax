"""Create a manual review sample from an external HuggingFace dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from baymax.models.external_dataset import DEFAULT_EXTERNAL_DATASET_ID, ExternalDatasetLoadError
from baymax.models.external_review import ExternalReviewConfig, create_external_review_sample

DEFAULT_OUTPUT_PATH = Path("data/sft/v1/xlam-review-sample.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-id",
        default=DEFAULT_EXTERNAL_DATASET_ID,
        help="HuggingFace dataset ID to sample.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional HuggingFace dataset revision/commit SHA. If omitted, it is resolved.",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split to sample.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Number of rows to include in the review sample.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Random seed for deterministic sampling.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap on rows scanned before sampling. Useful for quick smoke tests.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write the review JSON.",
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Download/load the dataset locally instead of streaming rows.",
    )
    args = parser.parse_args()

    config = ExternalReviewConfig(
        dataset_id=args.dataset_id,
        revision=args.revision,
        split=args.split,
        sample_size=args.sample_size,
        seed=args.seed,
        max_rows=args.max_rows,
        streaming=not args.no_streaming,
    )

    try:
        sample = create_external_review_sample(config)
    except ExternalDatasetLoadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sample.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(sample.rows)} review rows to {args.output}")
    print(f"Scanned {sample.loaded_rows} source rows from {sample.dataset_id}@{sample.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
