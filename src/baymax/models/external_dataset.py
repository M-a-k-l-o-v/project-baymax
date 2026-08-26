"""External training dataset inspection helpers for Phase 2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_EXTERNAL_DATASET_ID = "Salesforce/xLAM-function-calling-60k"


class ExternalDatasetLoadError(RuntimeError):
    """Raised when an external dataset cannot be loaded."""


class ExternalDatasetConfig(BaseModel):
    """Configuration for loading an external HuggingFace dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = DEFAULT_EXTERNAL_DATASET_ID
    revision: str | None = None
    split: str | None = None
    preview_rows: int = Field(default=3, ge=0, le=25)
    streaming: bool = True


class DatasetSplitSummary(BaseModel):
    """Small, serializable summary of one dataset split."""

    model_config = ConfigDict(extra="forbid")

    name: str
    row_count: int | None
    columns: list[str]
    preview: list[dict[str, Any]] = Field(default_factory=list)


class ExternalDatasetSummary(BaseModel):
    """Small, serializable summary of an external dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    revision: str | None
    splits: list[DatasetSplitSummary]


def resolve_huggingface_dataset_revision(dataset_id: str) -> str:
    """Return the current HuggingFace SHA for a dataset."""

    try:
        from huggingface_hub import HfApi
    except ImportError as error:  # pragma: no cover - covered by dependency path in CI
        raise RuntimeError(
            "Install huggingface_hub to resolve dataset revisions: "
            "python -m pip install huggingface_hub"
        ) from error

    dataset_info = HfApi().dataset_info(repo_id=dataset_id)
    sha = getattr(dataset_info, "sha", None)
    if not isinstance(sha, str) or not sha:
        raise RuntimeError(f"HuggingFace did not return a revision SHA for {dataset_id!r}.")

    return sha


def load_huggingface_dataset(config: ExternalDatasetConfig) -> Any:
    """Load a HuggingFace dataset using the configured ID, revision, and split."""

    try:
        from datasets import load_dataset
    except ImportError as error:  # pragma: no cover - covered by dependency path in CI
        raise RuntimeError(
            "Install datasets to load external training data: "
            "python -m pip install datasets huggingface_hub"
        ) from error

    kwargs: dict[str, Any] = {}
    if config.revision is not None:
        kwargs["revision"] = config.revision
    if config.split is not None:
        kwargs["split"] = config.split
    kwargs["streaming"] = config.streaming

    try:
        return load_dataset(config.dataset_id, **kwargs)
    except Exception as error:
        message = str(error)
        if "gated dataset" in message or "authenticated" in message:
            raise ExternalDatasetLoadError(
                f"Dataset {config.dataset_id!r} requires HuggingFace authentication. "
                "Set HF_TOKEN in the environment or run `huggingface-cli login`, then retry."
            ) from error

        raise ExternalDatasetLoadError(f"Failed to load dataset {config.dataset_id!r}.") from error


def summarize_external_dataset(
    dataset: Any,
    *,
    dataset_id: str,
    revision: str | None,
    preview_rows: int,
    split_name: str | None = None,
) -> ExternalDatasetSummary:
    """Summarize an already-loaded dataset or dataset dict."""

    splits: list[DatasetSplitSummary]
    if _looks_like_dataset_dict(dataset):
        splits = [
            _summarize_split(name=str(name), split=split, preview_rows=preview_rows)
            for name, split in dataset.items()
        ]
    else:
        splits = [
            _summarize_split(
                name=split_name or "default",
                split=dataset,
                preview_rows=preview_rows,
            )
        ]

    return ExternalDatasetSummary(
        dataset_id=dataset_id,
        revision=revision,
        splits=splits,
    )


def inspect_huggingface_dataset(config: ExternalDatasetConfig) -> ExternalDatasetSummary:
    """Resolve revision, load the dataset, and return a compact summary."""

    revision = config.revision or resolve_huggingface_dataset_revision(config.dataset_id)
    loaded_dataset = load_huggingface_dataset(config.model_copy(update={"revision": revision}))
    return summarize_external_dataset(
        loaded_dataset,
        dataset_id=config.dataset_id,
        revision=revision,
        preview_rows=config.preview_rows,
        split_name=config.split,
    )


def _looks_like_dataset_dict(dataset: Any) -> bool:
    if _is_huggingface_dataset_dict(dataset):
        return True
    if _looks_like_dataset_split(dataset):
        return False

    return isinstance(dataset, Mapping) or (
        callable(getattr(dataset, "items", None)) and callable(getattr(dataset, "keys", None))
    )


def _is_huggingface_dataset_dict(dataset: Any) -> bool:
    try:
        from datasets import DatasetDict, IterableDatasetDict
    except ImportError:  # pragma: no cover - dependency is available in normal use
        return False

    return isinstance(dataset, DatasetDict | IterableDatasetDict)


def _looks_like_dataset_split(dataset: Any) -> bool:
    return hasattr(dataset, "column_names") or hasattr(dataset, "num_rows")


def _summarize_split(
    *,
    name: str,
    split: Any,
    preview_rows: int,
) -> DatasetSplitSummary:
    preview = _preview_rows(split, preview_rows)
    return DatasetSplitSummary(
        name=name,
        row_count=_row_count(split),
        columns=_column_names(split) or _column_names_from_preview(preview),
        preview=preview,
    )


def _row_count(split: Any) -> int | None:
    row_count = getattr(split, "num_rows", None)
    if isinstance(row_count, int):
        return row_count

    try:
        return len(split)
    except TypeError:
        return None


def _column_names(split: Any) -> list[str]:
    column_names = getattr(split, "column_names", None)
    if isinstance(column_names, list):
        return [str(column) for column in column_names]

    if isinstance(split, Sequence) and split:
        first_row = split[0]
        if isinstance(first_row, Mapping):
            return [str(column) for column in first_row.keys()]

    return []


def _column_names_from_preview(preview: list[dict[str, Any]]) -> list[str]:
    if not preview:
        return []

    return list(preview[0].keys())


def _preview_rows(split: Any, preview_rows: int) -> list[dict[str, Any]]:
    if preview_rows == 0:
        return []

    row_count = _row_count(split)
    limit = min(preview_rows, row_count) if row_count is not None else preview_rows
    if limit <= 0:
        return []

    if hasattr(split, "take"):
        rows = _normalize_preview_rows(split.take(limit))
    elif hasattr(split, "select"):
        rows = _normalize_preview_rows(split.select(range(limit)))
    elif isinstance(split, Sequence):
        rows = _normalize_preview_rows(split[:limit])
    elif isinstance(split, Iterable):
        rows = []
        for index, row in enumerate(split):
            if index >= limit:
                break
            rows.append(row)
    else:
        rows = []

    return [_as_plain_dict(row) for row in rows]


def _normalize_preview_rows(selected_rows: Any) -> list[Any]:
    if isinstance(selected_rows, Mapping):
        return _rows_from_column_mapping(selected_rows)
    if isinstance(selected_rows, Sequence) and not isinstance(selected_rows, str):
        return list(selected_rows)
    if isinstance(selected_rows, Iterable) and not isinstance(selected_rows, str):
        return list(selected_rows)

    return [selected_rows]


def _rows_from_column_mapping(columns: Mapping[str, Any]) -> list[dict[str, Any]]:
    row_count = _column_mapping_row_count(columns)
    return [
        {
            str(column_name): column_values[row_index]
            for column_name, column_values in columns.items()
        }
        for row_index in range(row_count)
    ]


def _column_mapping_row_count(columns: Mapping[str, Any]) -> int:
    row_counts = [
        len(column_values)
        for column_values in columns.values()
        if isinstance(column_values, Sequence) and not isinstance(column_values, str)
    ]
    if not row_counts:
        return 0

    return min(row_counts)


def _as_plain_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return {str(key): value for key, value in row.items()}

    return {"value": row}
