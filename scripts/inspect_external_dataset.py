"""Inspect an external HuggingFace dataset for Phase 2 data planning."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from baymax.models.external_dataset import (
    DEFAULT_EXTERNAL_DATASET_ID,
    ExternalDatasetConfig,
    ExternalDatasetLoadError,
    inspect_huggingface_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-id",
        default=DEFAULT_EXTERNAL_DATASET_ID,
        help="HuggingFace dataset ID to inspect.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional HuggingFace dataset revision/commit SHA. If omitted, it is resolved.",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Optional split name to load. If omitted, all available splits are summarized.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=3,
        help="Number of example rows to include per split.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the JSON summary.",
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Download/load the dataset locally instead of streaming preview rows.",
    )
    args = parser.parse_args()

    config = ExternalDatasetConfig(
        dataset_id=args.dataset_id,
        revision=args.revision,
        split=args.split,
        preview_rows=args.preview_rows,
        streaming=not args.no_streaming,
    )
    try:
        summary = inspect_huggingface_dataset(config)
    except ExternalDatasetLoadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    output = summary.model_dump_json(indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
