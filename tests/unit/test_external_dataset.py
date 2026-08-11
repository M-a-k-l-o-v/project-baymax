from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import overload

import pytest
from pydantic import ValidationError

from baymax.models.external_dataset import (
    DEFAULT_EXTERNAL_DATASET_ID,
    ExternalDatasetConfig,
    summarize_external_dataset,
)


class FakeDatasetSplit:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.column_names = list(rows[0].keys()) if rows else []
        self.num_rows = len(rows)

    def select(self, indexes: range) -> list[dict[str, object]]:
        return [self._rows[index] for index in indexes]


class FakeIterableDatasetSplit:
    column_names = ["query", "answers"]

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __iter__(self) -> Iterator[dict[str, object]]:
        return iter(self._rows)


class FakeIterableDatasetSplitWithoutColumns:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __iter__(self) -> Iterator[dict[str, object]]:
        return iter(self._rows)


class FakeColumnarSliceDataset(Sequence[dict[str, object]]):
    column_names = ["query", "answers"]

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    @overload
    def __getitem__(self, index: int) -> dict[str, object]: ...

    @overload
    def __getitem__(self, index: slice) -> dict[str, list[object]]: ...

    def __getitem__(self, index: int | slice) -> dict[str, object] | dict[str, list[object]]:
        if isinstance(index, slice):
            rows = self._rows[index]
            return {
                "query": [row["query"] for row in rows],
                "answers": [row["answers"] for row in rows],
            }

        return self._rows[index]


class FakeColumnarTakeDataset:
    column_names = ["query", "answers"]

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def take(self, limit: int) -> dict[str, list[object]]:
        rows = self._rows[:limit]
        return {
            "query": [row["query"] for row in rows],
            "answers": [row["answers"] for row in rows],
        }


class FakeDatasetDict:
    def __init__(self, splits: dict[str, object]) -> None:
        self._splits = splits

    def keys(self) -> object:
        return self._splits.keys()

    def items(self) -> object:
        return self._splits.items()

    def __iter__(self) -> Iterator[str]:
        return iter(self._splits)

    def __len__(self) -> int:
        return len(self._splits)


def test_external_dataset_config_defaults_to_xlam() -> None:
    config = ExternalDatasetConfig()

    assert config.dataset_id == DEFAULT_EXTERNAL_DATASET_ID
    assert config.revision is None
    assert config.split is None
    assert config.preview_rows == 3
    assert config.streaming is True


def test_external_dataset_config_rejects_negative_preview_rows() -> None:
    with pytest.raises(ValidationError):
        ExternalDatasetConfig(preview_rows=-1)


def test_summarize_external_dataset_handles_dataset_dict() -> None:
    dataset = {
        "train": FakeDatasetSplit(
            [
                {"query": "Schedule study", "answers": [{"name": "create_event"}]},
                {"query": "Email Maya", "answers": [{"name": "send_email"}]},
            ]
        ),
        "validation": FakeDatasetSplit([{"query": "Create task", "answers": []}]),
    }

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=1,
    )

    assert summary.dataset_id == "example/tool-dataset"
    assert summary.revision == "abc123"
    assert [split.name for split in summary.splits] == ["train", "validation"]
    assert summary.splits[0].row_count == 2
    assert summary.splits[0].columns == ["query", "answers"]
    assert summary.splits[0].preview == [
        {"query": "Schedule study", "answers": [{"name": "create_event"}]}
    ]


def test_summarize_external_dataset_handles_dict_like_dataset_wrapper() -> None:
    dataset = FakeDatasetDict(
        {
            "train": FakeDatasetSplit(
                [{"query": "Schedule study", "answers": [{"name": "create_event"}]}]
            )
        }
    )

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=1,
    )

    assert [split.name for split in summary.splits] == ["train"]
    assert summary.splits[0].preview == [
        {"query": "Schedule study", "answers": [{"name": "create_event"}]}
    ]


def test_summarize_external_dataset_handles_huggingface_iterable_dataset_dict() -> None:
    from datasets import IterableDataset, IterableDatasetDict

    def rows() -> Iterator[dict[str, object]]:
        yield {"query": "Schedule study", "answers": [{"name": "create_event"}]}

    dataset = IterableDatasetDict(
        [
            ("train", IterableDataset.from_generator(rows)),
        ]
    )

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=1,
    )

    assert [split.name for split in summary.splits] == ["train"]
    assert summary.splits[0].preview == [
        {"query": "Schedule study", "answers": [{"name": "create_event"}]}
    ]


def test_summarize_external_dataset_handles_single_split_sequence() -> None:
    dataset = [
        {"instruction": "Draft an email", "output": {"name": "email"}},
        {"instruction": "Create task", "output": {"name": "task"}},
    ]

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision=None,
        preview_rows=2,
        split_name="train",
    )

    assert len(summary.splits) == 1
    assert summary.splits[0].name == "train"
    assert summary.splits[0].row_count == 2
    assert summary.splits[0].columns == ["instruction", "output"]
    assert summary.splits[0].preview == dataset


def test_summarize_external_dataset_can_skip_preview_rows() -> None:
    dataset = [("not", "a mapping")]

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision=None,
        preview_rows=0,
    )

    assert summary.splits[0].preview == []


def test_summarize_external_dataset_handles_streaming_iterable() -> None:
    dataset = FakeIterableDatasetSplit(
        [
            {"query": "Schedule study", "answers": [{"name": "create_event"}]},
            {"query": "Email Maya", "answers": [{"name": "send_email"}]},
        ]
    )

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=1,
        split_name="train",
    )

    assert summary.splits[0].row_count is None
    assert summary.splits[0].columns == ["query", "answers"]
    assert summary.splits[0].preview == [
        {"query": "Schedule study", "answers": [{"name": "create_event"}]}
    ]


def test_summarize_external_dataset_infers_columns_from_preview() -> None:
    dataset = FakeIterableDatasetSplitWithoutColumns(
        [
            {"id": 1, "query": "Schedule study", "answers": [], "tools": []},
        ]
    )

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=1,
        split_name="train",
    )

    assert summary.splits[0].columns == ["id", "query", "answers", "tools"]


def test_summarize_external_dataset_handles_columnar_slice_preview() -> None:
    dataset = FakeColumnarSliceDataset(
        [
            {"query": "Schedule study", "answers": [{"name": "create_event"}]},
            {"query": "Email Maya", "answers": [{"name": "send_email"}]},
        ]
    )

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=2,
        split_name="train",
    )

    assert summary.splits[0].preview == [
        {"query": "Schedule study", "answers": [{"name": "create_event"}]},
        {"query": "Email Maya", "answers": [{"name": "send_email"}]},
    ]


def test_summarize_external_dataset_handles_columnar_take_preview() -> None:
    dataset = FakeColumnarTakeDataset(
        [
            {"query": "Schedule study", "answers": [{"name": "create_event"}]},
            {"query": "Email Maya", "answers": [{"name": "send_email"}]},
        ]
    )

    summary = summarize_external_dataset(
        dataset,
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=2,
        split_name="train",
    )

    assert summary.splits[0].preview == [
        {"query": "Schedule study", "answers": [{"name": "create_event"}]},
        {"query": "Email Maya", "answers": [{"name": "send_email"}]},
    ]


def test_summarize_external_dataset_keeps_scalar_preview_rows_inspectable() -> None:
    summary = summarize_external_dataset(
        ["not a mapping"],
        dataset_id="example/tool-dataset",
        revision="abc123",
        preview_rows=1,
        split_name="train",
    )

    assert summary.splits[0].preview == [{"value": "not a mapping"}]
