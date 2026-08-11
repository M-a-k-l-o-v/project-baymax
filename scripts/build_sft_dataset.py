"""Build Qwen-style SFT JSONL files from an external HuggingFace tool-use dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from baymax.models.external_dataset import DEFAULT_EXTERNAL_DATASET_ID, ExternalDatasetLoadError
from baymax.models.sft_dataset import (
    SFTBuildConfig,
    SFTSplitRatios,
    build_sft_dataset_from_huggingface,
)

DEFAULT_OUTPUT_DIR = Path("data/sft/v1/xlam")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-id",
        default=DEFAULT_EXTERNAL_DATASET_ID,
        help="HuggingFace dataset ID to convert.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional HuggingFace dataset revision/commit SHA. If omitted, it is resolved.",
    )
    parser.add_argument(
        "--source-split",
        default="train",
        help="Source dataset split to convert.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for train.jsonl, validation.jsonl, test.jsonl, and split-manifest.json.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Seed used for deterministic split assignment.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap on source rows to scan. Useful for smoke tests.",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="Train split ratio.",
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.2,
        help="Validation split ratio.",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.1,
        help="Test split ratio.",
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Download/load the dataset locally instead of streaming rows.",
    )
    args = parser.parse_args()

    try:
        config = SFTBuildConfig(
            dataset_id=args.dataset_id,
            revision=args.revision,
            source_split=args.source_split,
            output_dir=args.output_dir,
            seed=args.seed,
            max_rows=args.max_rows,
            split_ratios=SFTSplitRatios(
                train=args.train_ratio,
                validation=args.validation_ratio,
                test=args.test_ratio,
            ),
            streaming=not args.no_streaming,
        )
    except ValidationError as error:
        print(f"error: invalid SFT build config: {error}", file=sys.stderr)
        return 1

    try:
        manifest = build_sft_dataset_from_huggingface(config)
    except ExternalDatasetLoadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote SFT dataset to {config.output_dir}")
    print(
        "Counts: "
        f"train={manifest.splits['train'].count}, "
        f"validation={manifest.splits['validation'].count}, "
        f"test={manifest.splits['test'].count}, "
        f"skipped={len(manifest.skipped_rows)}"
    )
    print(f"Config hash: {manifest.config_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
