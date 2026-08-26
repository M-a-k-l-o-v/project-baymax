"""Manual review sampling helpers for external Phase 2 training datasets."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from baymax.models.external_dataset import (
    DEFAULT_EXTERNAL_DATASET_ID,
    ExternalDatasetConfig,
    load_huggingface_dataset,
    resolve_huggingface_dataset_revision,
)

ReviewLabel = Literal["correct", "wrong_tool", "wrong_args", "malformed"]
REVIEW_LABELS: tuple[ReviewLabel, ...] = ("correct", "wrong_tool", "wrong_args", "malformed")
DEFAULT_REJECTION_THRESHOLD = 0.25


class ExternalReviewConfig(BaseModel):
    """Configuration for creating a manual review sample."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = DEFAULT_EXTERNAL_DATASET_ID
    revision: str | None = None
    split: str = "train"
    sample_size: int = Field(default=100, ge=1, le=10_000)
    seed: int = 1
    max_rows: int | None = Field(default=None, ge=1)
    streaming: bool = True


class ExternalReviewRow(BaseModel):
    """One sampled external dataset row prepared for human review."""

    model_config = ConfigDict(extra="forbid")

    source_index: int
    source_row_id: int | str | None = None
    query: str
    answers: Any | None = None
    tools: Any | None = None
    raw_answers: Any | None = None
    raw_tools: Any | None = None
    parse_errors: list[str] = Field(default_factory=list)
    review_label: ReviewLabel | None = None
    review_notes: str = ""


class ExternalReviewSample(BaseModel):
    """A deterministic manual review sample from an external dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    revision: str | None
    split: str
    seed: int
    requested_sample_size: int
    loaded_rows: int
    label_options: list[ReviewLabel]
    rows: list[ExternalReviewRow]


class ExternalReviewSummary(BaseModel):
    """Quality summary for a manually reviewed external dataset sample."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    revision: str | None
    split: str
    total_rows: int
    reviewed_rows: int
    unreviewed_rows: int
    label_counts: dict[ReviewLabel, int]
    error_rows: int
    parse_error_rows: int
    error_rate: float | None
    rejection_threshold: float
    ready_for_decision: bool
    reject_dataset: bool | None


def create_external_review_sample(config: ExternalReviewConfig) -> ExternalReviewSample:
    """Load a HuggingFace dataset split and create a deterministic review sample."""

    revision = config.revision or resolve_huggingface_dataset_revision(config.dataset_id)
    dataset = load_huggingface_dataset(
        ExternalDatasetConfig(
            dataset_id=config.dataset_id,
            revision=revision,
            split=config.split,
            preview_rows=0,
            streaming=config.streaming,
        )
    )

    return build_external_review_sample(
        dataset,
        dataset_id=config.dataset_id,
        revision=revision,
        split=config.split,
        sample_size=config.sample_size,
        seed=config.seed,
        max_rows=config.max_rows,
    )


def build_external_review_sample(
    rows: Iterable[Any],
    *,
    dataset_id: str,
    revision: str | None,
    split: str,
    sample_size: int,
    seed: int,
    max_rows: int | None = None,
) -> ExternalReviewSample:
    """Build a deterministic review sample from already-loaded dataset rows."""

    loaded_rows, sampled_rows = _reservoir_sample(
        rows,
        sample_size=sample_size,
        seed=seed,
        max_rows=max_rows,
    )
    review_rows = [
        _review_row_from_source(source_index=source_index, row=row)
        for source_index, row in sorted(sampled_rows, key=lambda item: item[0])
    ]

    return ExternalReviewSample(
        dataset_id=dataset_id,
        revision=revision,
        split=split,
        seed=seed,
        requested_sample_size=sample_size,
        loaded_rows=loaded_rows,
        label_options=list(REVIEW_LABELS),
        rows=review_rows,
    )


def summarize_external_review_sample(
    sample: ExternalReviewSample,
    *,
    rejection_threshold: float = DEFAULT_REJECTION_THRESHOLD,
) -> ExternalReviewSummary:
    """Summarize manual review labels and apply the external-data quality gate."""

    label_counts: dict[ReviewLabel, int] = {label: 0 for label in REVIEW_LABELS}
    for row in sample.rows:
        if row.review_label is not None:
            label_counts[row.review_label] += 1

    total_rows = len(sample.rows)
    reviewed_rows = sum(label_counts.values())
    unreviewed_rows = total_rows - reviewed_rows
    error_rows = reviewed_rows - label_counts["correct"]
    error_rate = error_rows / reviewed_rows if reviewed_rows else None
    ready_for_decision = total_rows > 0 and unreviewed_rows == 0
    reject_dataset = error_rate > rejection_threshold if error_rate is not None else None

    return ExternalReviewSummary(
        dataset_id=sample.dataset_id,
        revision=sample.revision,
        split=sample.split,
        total_rows=total_rows,
        reviewed_rows=reviewed_rows,
        unreviewed_rows=unreviewed_rows,
        label_counts=label_counts,
        error_rows=error_rows,
        parse_error_rows=sum(1 for row in sample.rows if row.parse_errors),
        error_rate=error_rate,
        rejection_threshold=rejection_threshold,
        ready_for_decision=ready_for_decision,
        reject_dataset=reject_dataset if ready_for_decision else None,
    )


def _reservoir_sample(
    rows: Iterable[Any],
    *,
    sample_size: int,
    seed: int,
    max_rows: int | None,
) -> tuple[int, list[tuple[int, Any]]]:
    rng = random.Random(seed)
    sampled_rows: list[tuple[int, Any]] = []
    loaded_rows = 0

    for source_index, row in enumerate(rows):
        if max_rows is not None and loaded_rows >= max_rows:
            break

        loaded_rows += 1
        if len(sampled_rows) < sample_size:
            sampled_rows.append((source_index, row))
            continue

        replacement_index = rng.randrange(loaded_rows)
        if replacement_index < sample_size:
            sampled_rows[replacement_index] = (source_index, row)

    return loaded_rows, sampled_rows


def _review_row_from_source(*, source_index: int, row: Any) -> ExternalReviewRow:
    if not isinstance(row, Mapping):
        return ExternalReviewRow(
            source_index=source_index,
            query="",
            parse_errors=[f"row: expected mapping, got {type(row).__name__}"],
        )

    raw_answers = row.get("answers")
    raw_tools = row.get("tools")
    answers, answer_error = _parse_json_list_field("answers", raw_answers)
    tools, tool_error = _parse_json_list_field("tools", raw_tools)
    parse_errors = [error for error in (answer_error, tool_error) if error is not None]

    return ExternalReviewRow(
        source_index=source_index,
        source_row_id=_source_row_id(row.get("id")),
        query=_string_field(row.get("query")),
        answers=answers,
        tools=tools,
        raw_answers=raw_answers,
        raw_tools=raw_tools,
        parse_errors=parse_errors,
    )


def _parse_json_list_field(field_name: str, value: Any) -> tuple[Any | None, str | None]:
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError as error:
            return None, f"{field_name}: invalid JSON at char {error.pos}: {error.msg}"
    else:
        parsed_value = value

    if parsed_value is None:
        return None, f"{field_name}: missing"
    if not isinstance(parsed_value, list):
        return parsed_value, f"{field_name}: expected list, got {type(parsed_value).__name__}"

    return parsed_value, None


def _source_row_id(value: Any) -> int | str | None:
    if isinstance(value, (int, str)):
        return value
    if value is None:
        return None

    return str(value)


def _string_field(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""

    return str(value)
