from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from baymax.models.sft_dataset import (
    DEFAULT_SFT_SYSTEM_PROMPT,
    SFTBuildConfig,
    SFTConversionError,
    SFTSplitRatios,
    build_sft_dataset_from_rows,
    convert_xlam_row_to_sft_example,
    sft_build_config_hash,
)


def test_sft_split_ratios_reject_non_unit_total() -> None:
    with pytest.raises(ValidationError):
        SFTSplitRatios(train=0.8, validation=0.2, test=0.2)


def test_convert_xlam_row_to_sft_example_uses_chat_messages_format() -> None:
    row = {
        "query": "Email Maya the notes.",
        "answers": '[{"name": "send_email", "arguments": {"recipient": "maya@example.com"}}]',
        "tools": '[{"name": "send_email", "parameters": {"recipient": {"type": "str"}}}]',
    }

    example = convert_xlam_row_to_sft_example(row, system_prompt=DEFAULT_SFT_SYSTEM_PROMPT)

    assert [message.role for message in example.messages] == ["system", "user", "assistant"]
    assert example.messages[0].content == DEFAULT_SFT_SYSTEM_PROMPT
    assert "Available tools:" in example.messages[1].content
    assert "Email Maya the notes." in example.messages[1].content
    assert json.loads(example.messages[2].content) == [
        {"name": "send_email", "arguments": {"recipient": "maya@example.com"}}
    ]


def test_convert_xlam_row_to_sft_example_rejects_malformed_answers() -> None:
    row = {
        "query": "Email Maya the notes.",
        "answers": "[not json]",
        "tools": "[]",
    }

    with pytest.raises(SFTConversionError, match="answers: invalid JSON"):
        convert_xlam_row_to_sft_example(row, system_prompt=DEFAULT_SFT_SYSTEM_PROMPT)


def test_build_sft_dataset_from_rows_writes_splits_and_manifest(tmp_path: Path) -> None:
    rows = [_xlam_row(index) for index in range(10)]
    config = SFTBuildConfig(
        dataset_id="example/tool-dataset",
        revision="abc123",
        output_dir=tmp_path,
        seed=123,
    )

    manifest = build_sft_dataset_from_rows(rows, config=config)

    assert manifest.loaded_rows == 10
    assert manifest.converted_rows == 10
    assert manifest.skipped_rows == []
    assert manifest.splits["train"].count == 7
    assert manifest.splits["validation"].count == 2
    assert manifest.splits["test"].count == 1
    assert (tmp_path / "train.jsonl").exists()
    assert (tmp_path / "validation.jsonl").exists()
    assert (tmp_path / "test.jsonl").exists()
    assert (tmp_path / "split-manifest.json").exists()

    train_rows = _read_jsonl(tmp_path / "train.jsonl")
    assert list(train_rows[0].keys()) == ["messages"]
    messages = train_rows[0]["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 3

    split_indexes = {
        split_name: {row.source_index for row in split.source_rows}
        for split_name, split in manifest.splits.items()
    }
    assert split_indexes["train"].isdisjoint(split_indexes["validation"])
    assert split_indexes["train"].isdisjoint(split_indexes["test"])
    assert split_indexes["validation"].isdisjoint(split_indexes["test"])
    assert set.union(*split_indexes.values()) == set(range(10))


def test_build_sft_dataset_from_rows_skips_malformed_rows(tmp_path: Path) -> None:
    rows = [
        _xlam_row(0),
        {"id": 1, "query": "bad", "answers": "[not json]", "tools": "[]"},
        "not a mapping",
    ]
    config = SFTBuildConfig(
        dataset_id="example/tool-dataset",
        revision="abc123",
        output_dir=tmp_path,
        seed=1,
    )

    manifest = build_sft_dataset_from_rows(rows, config=config)

    assert manifest.loaded_rows == 3
    assert manifest.converted_rows == 1
    assert [row.source_index for row in manifest.skipped_rows] == [1, 2]
    assert "answers: invalid JSON" in manifest.skipped_rows[0].reason
    assert manifest.skipped_rows[1].reason == "expected mapping, got str"


def test_sft_build_config_hash_is_stable_and_changes_with_content() -> None:
    first_config = SFTBuildConfig(
        dataset_id="example/tool-dataset",
        revision="abc123",
        seed=1,
    )
    second_config = SFTBuildConfig(
        dataset_id="example/tool-dataset",
        revision="abc123",
        seed=1,
    )
    changed_config = SFTBuildConfig(
        dataset_id="example/tool-dataset",
        revision="abc123",
        seed=2,
    )

    assert sft_build_config_hash(first_config) == sft_build_config_hash(second_config)
    assert sft_build_config_hash(first_config) != sft_build_config_hash(changed_config)


def _xlam_row(index: int) -> dict[str, object]:
    return {
        "id": index,
        "query": f"Look up item {index}.",
        "answers": json.dumps(
            [{"name": "lookup_item", "arguments": {"item_id": index}}],
            separators=(",", ":"),
        ),
        "tools": json.dumps(
            [{"name": "lookup_item", "parameters": {"item_id": {"type": "int"}}}],
            separators=(",", ":"),
        ),
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
