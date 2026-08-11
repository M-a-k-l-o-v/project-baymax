"""SFT dataset conversion helpers for Phase 2 model training."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from baymax.models.external_dataset import (
    DEFAULT_EXTERNAL_DATASET_ID,
    ExternalDatasetConfig,
    load_huggingface_dataset,
    resolve_huggingface_dataset_revision,
)

SFT_FORMAT_VERSION = "qwen-chat-messages-v1"
DEFAULT_SFT_SYSTEM_PROMPT = (
    "You are BAYMAX's tool-calling planner. Given a user request and available tools, "
    "return only the JSON array of tool calls required to satisfy the request."
)
SplitName = Literal["train", "validation", "test"]


class SFTConversionError(ValueError):
    """Raised when an external row cannot be converted into an SFT example."""


class SFTSplitRatios(BaseModel):
    """Target train/validation/test split ratios."""

    model_config = ConfigDict(extra="forbid")

    train: float = Field(default=0.7, gt=0)
    validation: float = Field(default=0.2, gt=0)
    test: float = Field(default=0.1, gt=0)

    @model_validator(mode="after")
    def validate_total(self) -> SFTSplitRatios:
        total = self.train + self.validation + self.test
        if abs(total - 1.0) > 0.000001:
            raise ValueError("SFT split ratios must sum to 1.0.")

        return self


class SFTBuildConfig(BaseModel):
    """Configuration for building an SFT dataset from an external source."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = DEFAULT_EXTERNAL_DATASET_ID
    revision: str | None = None
    source_split: str = "train"
    output_dir: Path = Path("data/sft/v1/xlam")
    seed: int = 1
    max_rows: int | None = Field(default=None, ge=1)
    split_ratios: SFTSplitRatios = Field(default_factory=SFTSplitRatios)
    system_prompt: str = DEFAULT_SFT_SYSTEM_PROMPT
    streaming: bool = True


class SFTMessage(BaseModel):
    """One chat message in the Qwen-style SFT format."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class SFTExample(BaseModel):
    """One training example in chat messages format."""

    model_config = ConfigDict(extra="forbid")

    messages: list[SFTMessage]


class SFTSourceRowRef(BaseModel):
    """Source-row reference for split reproducibility."""

    model_config = ConfigDict(extra="forbid")

    source_index: int
    source_row_id: int | str | None
    row_hash: str


class SFTSkippedRow(BaseModel):
    """Source row that was skipped during conversion."""

    model_config = ConfigDict(extra="forbid")

    source_index: int
    source_row_id: int | str | None
    reason: str


class SFTSplitManifestEntry(BaseModel):
    """Manifest metadata for one output split."""

    model_config = ConfigDict(extra="forbid")

    path: str
    count: int
    source_rows: list[SFTSourceRowRef]


class SFTSplitManifest(BaseModel):
    """Reproducibility manifest for an SFT dataset build."""

    model_config = ConfigDict(extra="forbid")

    format_version: str
    config_hash: str
    dataset_id: str
    revision: str | None
    source_split: str
    seed: int
    max_rows: int | None
    split_ratios: SFTSplitRatios
    system_prompt_sha256: str
    output_dir: str
    splits: dict[SplitName, SFTSplitManifestEntry]
    loaded_rows: int
    converted_rows: int
    skipped_rows: list[SFTSkippedRow]


class PreparedSFTRow(BaseModel):
    """Converted row plus source metadata before final split writing."""

    model_config = ConfigDict(extra="forbid")

    source: SFTSourceRowRef
    example: SFTExample


def build_sft_dataset_from_huggingface(config: SFTBuildConfig) -> SFTSplitManifest:
    """Load the configured HuggingFace split and build SFT JSONL files."""

    revision = config.revision or resolve_huggingface_dataset_revision(config.dataset_id)
    dataset = load_huggingface_dataset(
        ExternalDatasetConfig(
            dataset_id=config.dataset_id,
            revision=revision,
            split=config.source_split,
            preview_rows=0,
            streaming=config.streaming,
        )
    )

    return build_sft_dataset_from_rows(
        dataset,
        config=config.model_copy(update={"revision": revision}),
    )


def build_sft_dataset_from_rows(
    rows: Iterable[Any],
    *,
    config: SFTBuildConfig,
) -> SFTSplitManifest:
    """Convert source rows, split them deterministically, and write JSONL outputs."""

    loaded_rows, prepared_rows, skipped_rows = _prepare_rows(rows, config=config)
    split_rows = _split_prepared_rows(prepared_rows, config.split_ratios)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    output_paths: dict[SplitName, Path] = {
        "train": config.output_dir / "train.jsonl",
        "validation": config.output_dir / "validation.jsonl",
        "test": config.output_dir / "test.jsonl",
    }
    for split_name, split_examples in split_rows.items():
        _write_jsonl(output_paths[split_name], [row.example for row in split_examples])

    manifest = SFTSplitManifest(
        format_version=SFT_FORMAT_VERSION,
        config_hash=sft_build_config_hash(config),
        dataset_id=config.dataset_id,
        revision=config.revision,
        source_split=config.source_split,
        seed=config.seed,
        max_rows=config.max_rows,
        split_ratios=config.split_ratios,
        system_prompt_sha256=_sha256_text(config.system_prompt),
        output_dir=str(config.output_dir),
        splits={
            split_name: SFTSplitManifestEntry(
                path=str(output_paths[split_name]),
                count=len(split_examples),
                source_rows=[row.source for row in split_examples],
            )
            for split_name, split_examples in split_rows.items()
        },
        loaded_rows=loaded_rows,
        converted_rows=len(prepared_rows),
        skipped_rows=skipped_rows,
    )
    manifest_path = config.output_dir / "split-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    return manifest


def convert_xlam_row_to_sft_example(row: Mapping[str, Any], *, system_prompt: str) -> SFTExample:
    """Convert one xLAM row into the chat messages SFT format."""

    query = _required_string(row, "query")
    answers = _required_json_list(row, "answers")
    tools = _required_json_list(row, "tools")

    return SFTExample(
        messages=[
            SFTMessage(role="system", content=system_prompt),
            SFTMessage(role="user", content=_user_message(query=query, tools=tools)),
            SFTMessage(role="assistant", content=_json_dumps(answers)),
        ]
    )


def sft_build_config_hash(config: SFTBuildConfig) -> str:
    """Return the stable SHA256 hash for content-affecting SFT build config."""

    hash_payload = {
        "dataset_id": config.dataset_id,
        "revision": config.revision,
        "source_split": config.source_split,
        "seed": config.seed,
        "max_rows": config.max_rows,
        "split_ratios": config.split_ratios.model_dump(mode="json"),
        "system_prompt": config.system_prompt,
        "format_version": SFT_FORMAT_VERSION,
    }
    return _sha256_json(hash_payload)


def _prepare_rows(
    rows: Iterable[Any],
    *,
    config: SFTBuildConfig,
) -> tuple[int, list[PreparedSFTRow], list[SFTSkippedRow]]:
    prepared_rows: list[PreparedSFTRow] = []
    skipped_rows: list[SFTSkippedRow] = []
    loaded_rows = 0

    for source_index, row in enumerate(rows):
        if config.max_rows is not None and loaded_rows >= config.max_rows:
            break

        loaded_rows += 1
        source_row_id = _source_row_id(row.get("id")) if isinstance(row, Mapping) else None
        try:
            if not isinstance(row, Mapping):
                raise SFTConversionError(f"expected mapping, got {type(row).__name__}")

            example = convert_xlam_row_to_sft_example(row, system_prompt=config.system_prompt)
        except SFTConversionError as error:
            skipped_rows.append(
                SFTSkippedRow(
                    source_index=source_index,
                    source_row_id=source_row_id,
                    reason=str(error),
                )
            )
            continue

        prepared_rows.append(
            PreparedSFTRow(
                source=SFTSourceRowRef(
                    source_index=source_index,
                    source_row_id=source_row_id,
                    row_hash=_split_row_hash(
                        seed=config.seed,
                        source_index=source_index,
                        source_row_id=source_row_id,
                    ),
                ),
                example=example,
            )
        )

    return loaded_rows, prepared_rows, skipped_rows


def _split_prepared_rows(
    prepared_rows: list[PreparedSFTRow],
    split_ratios: SFTSplitRatios,
) -> dict[SplitName, list[PreparedSFTRow]]:
    sorted_rows = sorted(prepared_rows, key=lambda row: row.source.row_hash)
    total = len(sorted_rows)
    train_count = int(total * split_ratios.train)
    validation_count = int(total * split_ratios.validation)

    return {
        "train": sorted_rows[:train_count],
        "validation": sorted_rows[train_count : train_count + validation_count],
        "test": sorted_rows[train_count + validation_count :],
    }


def _write_jsonl(path: Path, examples: Iterable[SFTExample]) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        for example in examples:
            output_file.write(example.model_dump_json() + "\n")


def _user_message(*, query: str, tools: list[Any]) -> str:
    return "\n".join(
        [
            "Available tools:",
            _json_dumps(tools),
            "",
            "User request:",
            query,
        ]
    )


def _required_string(row: Mapping[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SFTConversionError(f"{field_name}: expected non-empty string")

    return value


def _required_json_list(row: Mapping[str, Any], field_name: str) -> list[Any]:
    value = row.get(field_name)
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError as error:
            raise SFTConversionError(
                f"{field_name}: invalid JSON at char {error.pos}: {error.msg}"
            ) from error
    else:
        parsed_value = value

    if not isinstance(parsed_value, list):
        raise SFTConversionError(f"{field_name}: expected list")

    return parsed_value


def _split_row_hash(*, seed: int, source_index: int, source_row_id: int | str | None) -> str:
    return _sha256_json(
        {
            "seed": seed,
            "source_index": source_index,
            "source_row_id": source_row_id,
        }
    )


def _sha256_json(value: Any) -> str:
    return _sha256_text(_json_dumps(value))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_row_id(value: Any) -> int | str | None:
    if isinstance(value, (int, str)):
        return value
    if value is None:
        return None

    return str(value)
