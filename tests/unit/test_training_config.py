from __future__ import annotations

from pathlib import Path

from baymax.models.training_config import (
    LoraTrainingConfig,
    OutputAdapterConfig,
    SFTTrainingConfig,
    TrainingDataConfig,
    TrainingHyperparameters,
    TrainingRuntimeConfig,
    load_training_config,
    training_config_hash,
    training_config_with_hash,
    validate_training_config,
    write_training_config,
)


def test_training_config_hash_is_stable_and_excludes_hash_field() -> None:
    config = _training_config()
    first_hash = training_config_hash(config)
    hashed_config = config.model_copy(update={"config_hash": "old-value"})

    assert training_config_hash(hashed_config) == first_hash
    assert training_config_with_hash(config).config_hash == first_hash


def test_validate_training_config_reports_hash_mismatch(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    write_training_config(config_path, _training_config(config_hash="incorrect"))

    report = validate_training_config(config_path)

    assert report.valid is False
    assert report.config_hash == "incorrect"
    assert report.expected_config_hash != "incorrect"
    assert report.issues[0].location == "config_hash"


def test_validate_training_config_accepts_matching_hash(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    write_training_config(config_path, training_config_with_hash(_training_config()))

    report = validate_training_config(config_path)

    assert report.valid is True
    assert report.issues == []


def test_validate_training_config_can_check_referenced_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    write_training_config(config_path, training_config_with_hash(_training_config()))

    report = validate_training_config(config_path, check_paths=True)

    assert report.valid is False
    assert {issue.location for issue in report.issues} == {
        "data.train_path",
        "data.validation_path",
        "data.test_path",
        "data.split_manifest_path",
        "data.validation_report_path",
        "data.eval_scenarios_path",
    }


def test_committed_qwen_lora_config_has_expected_lora_settings() -> None:
    config = load_training_config(Path("configs/sft/qwen2_5_1_5b_lora_v1.json"))
    report = validate_training_config(Path("configs/sft/qwen2_5_1_5b_lora_v1.json"))

    assert report.valid is True
    assert config.lora.r == 8
    assert config.lora.lora_alpha == 16
    assert config.lora.target_modules == ["q_proj", "v_proj"]
    assert config.lora.lora_dropout == 0.05
    assert config.lora.bias == "none"
    assert config.lora.task_type == "CAUSAL_LM"


def _training_config(*, config_hash: str | None = None) -> SFTTrainingConfig:
    return SFTTrainingConfig(
        config_name="test_config",
        config_hash=config_hash,
        base_model="Qwen/Qwen2.5-1.5B-Instruct",
        data=TrainingDataConfig(
            dataset_id="Salesforce/xLAM-function-calling-60k",
            revision="26d14ebfe18b1f7b524bd39b404b50af5dc97866",
            format_version="qwen-chat-messages-v1",
            train_path=Path("missing/train.jsonl"),
            validation_path=Path("missing/validation.jsonl"),
            test_path=Path("missing/test.jsonl"),
            split_manifest_path=Path("missing/split-manifest.json"),
            validation_report_path=Path("missing/validation-report.json"),
            eval_scenarios_path=Path("missing/scenarios"),
        ),
        lora=LoraTrainingConfig(
            r=8,
            lora_alpha=16,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        ),
        training=TrainingHyperparameters(
            learning_rate=0.0002,
            num_train_epochs=1,
            per_device_train_batch_size=2,
            per_device_eval_batch_size=2,
            gradient_accumulation_steps=8,
            max_sequence_length=2048,
            warmup_ratio=0.03,
            weight_decay=0.0,
            lr_scheduler_type="cosine",
            max_grad_norm=1.0,
            gradient_checkpointing=True,
            bf16=True,
            fp16=False,
            logging_steps=10,
            eval_steps=250,
            save_steps=250,
            save_total_limit=2,
        ),
        runtime=TrainingRuntimeConfig(
            seed=1,
            run_name="test_config",
            output_dir=Path("models/test_config"),
            model_registry_path=Path("models/models.json"),
            expected_adapter_path=Path("models/test_config/adapter"),
            report_to=[],
        ),
        output_adapter=OutputAdapterConfig(
            native_output_format="xlam_function_calling",
            baymax_boundary="AgentResponse",
            adapter_owner="Marv",
        ),
    )
