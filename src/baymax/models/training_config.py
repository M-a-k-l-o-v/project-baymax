"""Training configuration helpers for Phase 2 SFT runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingConfigIssue(BaseModel):
    """One issue found while validating a training config."""

    model_config = ConfigDict(extra="forbid")

    location: str
    message: str


class TrainingDataConfig(BaseModel):
    """Dataset paths and source identity for a training run."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    revision: str
    format_version: str
    train_path: Path
    validation_path: Path
    test_path: Path
    split_manifest_path: Path
    validation_report_path: Path
    eval_scenarios_path: Path


class LoraTrainingConfig(BaseModel):
    """LoRA adapter configuration."""

    model_config = ConfigDict(extra="forbid")

    r: int = Field(gt=0)
    lora_alpha: int = Field(gt=0)
    target_modules: list[str] = Field(min_length=1)
    lora_dropout: float = Field(ge=0, le=1)
    bias: Literal["none", "all", "lora_only"]
    task_type: Literal["CAUSAL_LM"]

    @field_validator("target_modules")
    @classmethod
    def validate_unique_target_modules(cls, target_modules: list[str]) -> list[str]:
        if len(target_modules) != len(set(target_modules)):
            raise ValueError("target_modules must not contain duplicates")

        return target_modules


class TrainingHyperparameters(BaseModel):
    """Core trainer hyperparameters for the first SFT run."""

    model_config = ConfigDict(extra="forbid")

    learning_rate: float = Field(gt=0)
    num_train_epochs: float = Field(gt=0)
    per_device_train_batch_size: int = Field(gt=0)
    per_device_eval_batch_size: int = Field(gt=0)
    gradient_accumulation_steps: int = Field(gt=0)
    max_sequence_length: int = Field(gt=0)
    warmup_ratio: float = Field(ge=0, le=1)
    weight_decay: float = Field(ge=0)
    lr_scheduler_type: Literal["linear", "cosine", "constant"]
    max_grad_norm: float = Field(gt=0)
    gradient_checkpointing: bool
    bf16: bool
    fp16: bool
    logging_steps: int = Field(gt=0)
    eval_steps: int = Field(gt=0)
    save_steps: int = Field(gt=0)
    save_total_limit: int = Field(gt=0)


class TrainingRuntimeConfig(BaseModel):
    """Runtime and output settings for a training run."""

    model_config = ConfigDict(extra="forbid")

    seed: int
    run_name: str
    output_dir: Path
    model_registry_path: Path
    expected_adapter_path: Path
    report_to: list[str] = Field(default_factory=list)


class OutputAdapterConfig(BaseModel):
    """Expected post-training adapter boundary."""

    model_config = ConfigDict(extra="forbid")

    native_output_format: Literal["xlam_function_calling"]
    baymax_boundary: Literal["AgentResponse"]
    adapter_owner: str


class SFTTrainingConfig(BaseModel):
    """Complete reproducible config for one SFT training run."""

    model_config = ConfigDict(extra="forbid")

    config_name: str
    config_hash: str | None = None
    base_model: str
    data: TrainingDataConfig
    lora: LoraTrainingConfig
    training: TrainingHyperparameters
    runtime: TrainingRuntimeConfig
    output_adapter: OutputAdapterConfig


class TrainingConfigValidationReport(BaseModel):
    """Validation result for a training config file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    valid: bool
    config_hash: str | None
    expected_config_hash: str
    issues: list[TrainingConfigIssue]


def load_training_config(path: Path) -> SFTTrainingConfig:
    """Load and validate a training config from JSON."""

    return SFTTrainingConfig.model_validate_json(path.read_text(encoding="utf-8"))


def training_config_hash(config: SFTTrainingConfig) -> str:
    """Return the stable SHA256 hash for content-affecting training config fields."""

    payload = config.model_dump(mode="json", exclude={"config_hash"})
    return _sha256_json(payload)


def training_config_with_hash(config: SFTTrainingConfig) -> SFTTrainingConfig:
    """Return a copy of the config with config_hash set to the computed hash."""

    return config.model_copy(update={"config_hash": training_config_hash(config)})


def validate_training_config(
    path: Path,
    *,
    check_paths: bool = False,
) -> TrainingConfigValidationReport:
    """Validate a training config and optionally verify referenced local paths exist."""

    config = load_training_config(path)
    expected_config_hash = training_config_hash(config)
    issues: list[TrainingConfigIssue] = []

    if config.config_hash != expected_config_hash:
        issues.append(
            TrainingConfigIssue(
                location="config_hash",
                message=(
                    f"config_hash is {config.config_hash!r}, expected {expected_config_hash!r}"
                ),
            )
        )

    if check_paths:
        issues.extend(_path_issues(config))

    return TrainingConfigValidationReport(
        path=str(path),
        valid=len(issues) == 0,
        config_hash=config.config_hash,
        expected_config_hash=expected_config_hash,
        issues=issues,
    )


def write_training_config(path: Path, config: SFTTrainingConfig) -> None:
    """Write a training config to JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _path_issues(config: SFTTrainingConfig) -> list[TrainingConfigIssue]:
    required_paths = {
        "data.train_path": config.data.train_path,
        "data.validation_path": config.data.validation_path,
        "data.test_path": config.data.test_path,
        "data.split_manifest_path": config.data.split_manifest_path,
        "data.validation_report_path": config.data.validation_report_path,
        "data.eval_scenarios_path": config.data.eval_scenarios_path,
    }
    issues: list[TrainingConfigIssue] = []

    for location, path in required_paths.items():
        if not path.exists():
            issues.append(
                TrainingConfigIssue(
                    location=location,
                    message=f"referenced path does not exist: {path}",
                )
            )

    return issues


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_json_dumps(value).encode("utf-8")).hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
