from __future__ import annotations

import json
from pathlib import Path

from baymax.models.sft_dataset import SFTBuildConfig, build_sft_dataset_from_rows
from baymax.models.sft_validation import validate_sft_dataset


def test_validate_sft_dataset_accepts_valid_generated_dataset(tmp_path: Path) -> None:
    _build_dataset(tmp_path, row_count=10)

    report = validate_sft_dataset(tmp_path)

    assert report.valid is True
    assert report.manifest_loaded is True
    assert report.revision == "abc123"
    assert report.config_hash is not None
    assert report.converted_rows == 10
    assert report.loaded_rows == 10
    assert report.skipped_row_count == 0
    assert report.splits["train"].actual_count == 7
    assert report.splits["validation"].actual_count == 2
    assert report.splits["test"].actual_count == 1


def test_validate_sft_dataset_reports_missing_manifest(tmp_path: Path) -> None:
    report = validate_sft_dataset(tmp_path)

    assert report.valid is False
    assert report.manifest_loaded is False
    assert report.issues[0].message == "split manifest not found"


def test_validate_sft_dataset_reports_invalid_jsonl_line(tmp_path: Path) -> None:
    _build_dataset(tmp_path, row_count=10)
    _append_text(tmp_path / "train.jsonl", "not json\n")

    report = validate_sft_dataset(tmp_path)

    assert report.valid is False
    assert report.splits["train"].invalid_json_lines == 1
    assert any("invalid JSON" in issue.message for issue in report.splits["train"].issues)
    assert any("manifest count is 7" in issue.message for issue in report.splits["train"].issues)


def test_validate_sft_dataset_reports_wrong_message_roles(tmp_path: Path) -> None:
    _build_dataset(tmp_path, row_count=10)
    train_path = tmp_path / "train.jsonl"
    rows = _read_jsonl(train_path)
    rows[0]["messages"] = _message_list(rows[0])[:2]
    _write_jsonl(train_path, rows)

    report = validate_sft_dataset(tmp_path)

    assert report.valid is False
    assert any(
        "messages must have roles" in issue.message for issue in report.splits["train"].issues
    )


def test_validate_sft_dataset_reports_invalid_assistant_json(tmp_path: Path) -> None:
    _build_dataset(tmp_path, row_count=10)
    train_path = tmp_path / "train.jsonl"
    rows = _read_jsonl(train_path)
    _message_list(rows[0])[-1]["content"] = "[not json]"
    _write_jsonl(train_path, rows)

    report = validate_sft_dataset(tmp_path)

    assert report.valid is False
    assert any(
        "assistant content is invalid JSON" in issue.message
        for issue in report.splits["train"].issues
    )


def test_validate_sft_dataset_reports_split_overlap(tmp_path: Path) -> None:
    _build_dataset(tmp_path, row_count=10)
    manifest_path = tmp_path / "split-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["splits"]["validation"]["source_rows"].append(
        manifest["splits"]["train"]["source_rows"][0]
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = validate_sft_dataset(tmp_path)

    assert report.valid is False
    assert any("appears in both train and validation" in issue.message for issue in report.issues)


def test_validate_sft_dataset_reports_missing_revision(tmp_path: Path) -> None:
    _build_dataset(tmp_path, row_count=10)
    manifest_path = tmp_path / "split-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["revision"] = None
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = validate_sft_dataset(tmp_path)

    assert report.valid is False
    assert any("dataset revision must be pinned" in issue.message for issue in report.issues)


def _build_dataset(output_dir: Path, *, row_count: int) -> None:
    rows = [_xlam_row(index) for index in range(row_count)]
    config = SFTBuildConfig(
        dataset_id="example/tool-dataset",
        revision="abc123",
        output_dir=output_dir,
        seed=1,
    )
    build_sft_dataset_from_rows(rows, config=config)


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


def _message_list(row: dict[str, object]) -> list[dict[str, object]]:
    messages = row["messages"]
    assert isinstance(messages, list)

    typed_messages: list[dict[str, object]] = []
    for message in messages:
        assert isinstance(message, dict)
        typed_messages.append(message)

    return typed_messages


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _append_text(path: Path, text: str) -> None:
    existing_text = path.read_text(encoding="utf-8")
    path.write_text(existing_text + text, encoding="utf-8")
