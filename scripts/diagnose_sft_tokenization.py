"""Diagnose SFT tokenization health before LoRA training."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from baymax.models.sft_training import (
    diagnose_sft_tokenization,
    load_sft_jsonl,
)
from baymax.models.training_config import SFTTrainingConfig, load_training_config

DEFAULT_CONFIG_PATH = Path("configs/sft/qwen2_5_1_5b_lora_v1.json")
SplitName = Literal["train", "validation", "test"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Training config JSON path.",
    )
    parser.add_argument(
        "--split",
        choices=["train", "validation", "test"],
        default="validation",
        help="SFT split to diagnose.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Cap rows for quick diagnostics.",
    )
    parser.add_argument(
        "--max-sequence-length",
        type=int,
        default=None,
        help="Override sequence length for this diagnostic.",
    )
    parser.add_argument(
        "--problem-row-limit",
        type=int,
        default=20,
        help="Maximum problem rows to include in the report.",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Pass trust_remote_code=True when loading the tokenizer.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path for the full diagnostic report.",
    )
    args = parser.parse_args()

    try:
        from transformers import AutoTokenizer
    except ImportError:
        print("error: missing transformers. Install training dependencies first.")
        return 1

    config = load_training_config(args.config)
    split_path = _split_path(config_path=args.split, config=config)
    rows = load_sft_jsonl(split_path, max_rows=args.max_rows)
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model,
        trust_remote_code=args.trust_remote_code,
    )
    max_sequence_length = args.max_sequence_length or config.training.max_sequence_length
    diagnostics = diagnose_sft_tokenization(
        rows=rows,
        tokenizer=tokenizer,
        max_sequence_length=max_sequence_length,
        max_problem_rows=args.problem_row_limit,
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(diagnostics.model_dump_json(indent=2) + "\n", encoding="utf-8")

    print(f"Split: {args.split}")
    print(f"Rows checked: {diagnostics.row_count}")
    print(f"Max sequence length: {diagnostics.max_sequence_length}")
    print(f"Rows with trainable labels: {diagnostics.rows_with_trainable_labels}")
    print(f"Rows without trainable labels: {diagnostics.rows_without_trainable_labels}")
    print(f"Truncated rows: {diagnostics.truncated_rows}")
    print(f"Prompt fills context rows: {diagnostics.prompt_fills_context_rows}")
    print(f"Total trainable label tokens: {diagnostics.total_trainable_label_tokens}")
    print(f"Min trainable label tokens: {diagnostics.min_trainable_label_tokens}")
    print(f"Max trainable label tokens: {diagnostics.max_trainable_label_tokens}")
    if diagnostics.problem_rows:
        print("Problem row examples:")
        for row in diagnostics.problem_rows:
            print(
                f"- row {row.row_index}: {', '.join(row.issues)} "
                f"({row.trainable_label_tokens} trainable labels)"
            )

    return 0


def _split_path(*, config_path: SplitName, config: SFTTrainingConfig) -> Path:
    if config_path == "train":
        return config.data.train_path
    if config_path == "validation":
        return config.data.validation_path

    return config.data.test_path


if __name__ == "__main__":
    raise SystemExit(main())
