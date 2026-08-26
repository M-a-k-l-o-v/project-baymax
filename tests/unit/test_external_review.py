from __future__ import annotations

from pydantic import ValidationError

from baymax.models.external_dataset import DEFAULT_EXTERNAL_DATASET_ID
from baymax.models.external_review import (
    ExternalReviewConfig,
    ExternalReviewRow,
    ExternalReviewSample,
    build_external_review_sample,
    summarize_external_review_sample,
)


def test_external_review_config_defaults_to_xlam_train() -> None:
    config = ExternalReviewConfig()

    assert config.dataset_id == DEFAULT_EXTERNAL_DATASET_ID
    assert config.revision is None
    assert config.split == "train"
    assert config.sample_size == 100
    assert config.seed == 1
    assert config.max_rows is None
    assert config.streaming is True


def test_external_review_config_rejects_empty_sample_size() -> None:
    try:
        ExternalReviewConfig(sample_size=0)
    except ValidationError as error:
        assert "sample_size" in str(error)
    else:
        raise AssertionError("Expected sample_size validation to fail.")


def test_build_external_review_sample_parses_xlam_json_fields() -> None:
    rows = [
        {
            "id": 12,
            "query": "Find giveaways",
            "answers": '[{"name": "live_giveaways_by_type", "arguments": {"type": "game"}}]',
            "tools": '[{"name": "live_giveaways_by_type", "parameters": {}}]',
        }
    ]

    sample = build_external_review_sample(
        rows,
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        sample_size=1,
        seed=1,
    )

    assert sample.dataset_id == "example/tool-dataset"
    assert sample.revision == "abc123"
    assert sample.split == "train"
    assert sample.loaded_rows == 1
    assert sample.label_options == ["correct", "wrong_tool", "wrong_args", "malformed"]
    assert sample.rows[0].source_index == 0
    assert sample.rows[0].source_row_id == 12
    assert sample.rows[0].query == "Find giveaways"
    assert sample.rows[0].answers == [
        {"name": "live_giveaways_by_type", "arguments": {"type": "game"}}
    ]
    assert sample.rows[0].tools == [{"name": "live_giveaways_by_type", "parameters": {}}]
    assert sample.rows[0].parse_errors == []
    assert sample.rows[0].review_label is None
    assert sample.rows[0].review_notes == ""


def test_build_external_review_sample_records_parse_errors() -> None:
    rows = [
        {
            "id": "bad-row",
            "query": "Find giveaways",
            "answers": "[not json]",
            "tools": '{"name": "not-a-list"}',
        }
    ]

    sample = build_external_review_sample(
        rows,
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        sample_size=1,
        seed=1,
    )

    assert sample.rows[0].parse_errors == [
        "answers: invalid JSON at char 1: Expecting value",
        "tools: expected list, got dict",
    ]


def test_build_external_review_sample_is_deterministic_for_same_seed() -> None:
    rows = [
        {"id": index, "query": str(index), "answers": "[]", "tools": "[]"} for index in range(20)
    ]

    first_sample = build_external_review_sample(
        rows,
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        sample_size=5,
        seed=42,
    )
    second_sample = build_external_review_sample(
        rows,
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        sample_size=5,
        seed=42,
    )

    first_indexes = [row.source_index for row in first_sample.rows]
    second_indexes = [row.source_index for row in second_sample.rows]
    assert first_indexes == second_indexes


def test_build_external_review_sample_honors_max_rows() -> None:
    rows = [
        {"id": index, "query": str(index), "answers": "[]", "tools": "[]"} for index in range(20)
    ]

    sample = build_external_review_sample(
        rows,
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        sample_size=10,
        seed=42,
        max_rows=3,
    )

    assert sample.loaded_rows == 3
    assert [row.source_index for row in sample.rows] == [0, 1, 2]


def test_build_external_review_sample_keeps_non_mapping_rows_reviewable() -> None:
    sample = build_external_review_sample(
        ["not a mapping"],
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        sample_size=1,
        seed=1,
    )

    assert sample.rows[0].parse_errors == ["row: expected mapping, got str"]


def test_summarize_external_review_sample_waits_for_complete_review() -> None:
    sample = ExternalReviewSample(
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        seed=1,
        requested_sample_size=2,
        loaded_rows=2,
        label_options=["correct", "wrong_tool", "wrong_args", "malformed"],
        rows=[
            ExternalReviewRow(source_index=0, query="one", review_label="correct"),
            ExternalReviewRow(source_index=1, query="two", review_label=None),
        ],
    )

    summary = summarize_external_review_sample(sample)

    assert summary.total_rows == 2
    assert summary.reviewed_rows == 1
    assert summary.unreviewed_rows == 1
    assert summary.error_rate == 0
    assert summary.ready_for_decision is False
    assert summary.reject_dataset is None


def test_summarize_external_review_sample_keeps_dataset_under_threshold() -> None:
    sample = ExternalReviewSample(
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        seed=1,
        requested_sample_size=4,
        loaded_rows=4,
        label_options=["correct", "wrong_tool", "wrong_args", "malformed"],
        rows=[
            ExternalReviewRow(source_index=0, query="one", review_label="correct"),
            ExternalReviewRow(source_index=1, query="two", review_label="correct"),
            ExternalReviewRow(source_index=2, query="three", review_label="correct"),
            ExternalReviewRow(source_index=3, query="four", review_label="wrong_args"),
        ],
    )

    summary = summarize_external_review_sample(sample, rejection_threshold=0.25)

    assert summary.label_counts == {
        "correct": 3,
        "wrong_tool": 0,
        "wrong_args": 1,
        "malformed": 0,
    }
    assert summary.error_rows == 1
    assert summary.error_rate == 0.25
    assert summary.ready_for_decision is True
    assert summary.reject_dataset is False


def test_summarize_external_review_sample_rejects_dataset_over_threshold() -> None:
    sample = ExternalReviewSample(
        dataset_id="example/tool-dataset",
        revision="abc123",
        split="train",
        seed=1,
        requested_sample_size=4,
        loaded_rows=4,
        label_options=["correct", "wrong_tool", "wrong_args", "malformed"],
        rows=[
            ExternalReviewRow(source_index=0, query="one", review_label="correct"),
            ExternalReviewRow(source_index=1, query="two", review_label="correct"),
            ExternalReviewRow(source_index=2, query="three", review_label="wrong_tool"),
            ExternalReviewRow(
                source_index=3,
                query="four",
                parse_errors=["answers: invalid JSON"],
                review_label="malformed",
            ),
        ],
    )

    summary = summarize_external_review_sample(sample, rejection_threshold=0.25)

    assert summary.error_rows == 2
    assert summary.parse_error_rows == 1
    assert summary.error_rate == 0.5
    assert summary.ready_for_decision is True
    assert summary.reject_dataset is True
