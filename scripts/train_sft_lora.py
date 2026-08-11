"""Train a LoRA SFT adapter from a Phase 2 training config."""

from __future__ import annotations

import argparse
from pathlib import Path

from baymax.models.sft_training import (
    SFTTrainingOverrides,
    TrainingDependencyError,
    run_sft_lora_training,
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
        "--dry-run",
        action="store_true",
        help="Validate config/data and print the training plan without loading the model.",
    )
    parser.add_argument(
        "--local-low-vram",
        action="store_true",
        help="Use conservative local settings for laptop GPUs.",
    )
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        help="Load the base model in 4-bit mode. Requires bitsandbytes support.",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow real training without CUDA. This is only practical for tiny smoke tests.",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Pass trust_remote_code=True when loading model/tokenizer.",
    )
    parser.add_argument(
        "--max-train-rows",
        type=int,
        default=None,
        help="Cap train rows for smoke runs.",
    )
    parser.add_argument(
        "--max-eval-rows",
        type=int,
        default=None,
        help="Cap validation rows for smoke runs.",
    )
    parser.add_argument(
        "--max-sequence-length",
        type=int,
        default=None,
        help="Override max sequence length for this run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory for this run.",
    )
    args = parser.parse_args()

    overrides = SFTTrainingOverrides(
        dry_run=args.dry_run,
        local_low_vram=args.local_low_vram,
        load_in_4bit=args.load_in_4bit,
        allow_cpu=args.allow_cpu,
        trust_remote_code=args.trust_remote_code,
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_sequence_length=args.max_sequence_length,
        output_dir=args.output_dir,
    )

    try:
        result = run_sft_lora_training(config_path=args.config, overrides=overrides)
    except TrainingDependencyError as error:
        print(f"error: {error}")
        return 1
    except ValueError as error:
        print(f"error: {error}")
        return 1
    except RuntimeError as error:
        print(f"error: {error}")
        return 1

    print(f"Dry run: {result.dry_run}")
    print(f"Trained: {result.trained}")
    print(f"Base model: {result.plan.base_model}")
    print(f"Train rows: {result.plan.train_rows}")
    print(f"Eval rows: {result.plan.eval_rows}")
    print(f"Max sequence length: {result.plan.max_sequence_length}")
    print(f"Train batch size: {result.plan.per_device_train_batch_size}")
    print(f"Gradient accumulation: {result.plan.gradient_accumulation_steps}")
    print(f"Output dir: {result.plan.output_dir}")
    print(f"Adapter path: {result.plan.adapter_path}")
    print(f"Config hash: {result.plan.config_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
