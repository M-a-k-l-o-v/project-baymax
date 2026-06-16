import pytest
from pydantic import ValidationError

from baymax.tools.fake_notion import FakeNotionAdapter


def test_create_task_appends_task_to_fake_state() -> None:
    adapter = FakeNotionAdapter.from_initial_state({"notion_tasks": []})

    result = adapter.create_task(
        title="Submit scholarship form",
        due_date="2026-05-25",
    )

    assert result.success is True
    assert result.tool == "notion.create_task"
    assert result.data == {"task_id": "task_fake_notion_001"}
    assert adapter.export_state() == {
        "notion_tasks": [
            {
                "id": "task_fake_notion_001",
                "title": "Submit scholarship form",
                "status": "open",
                "due_date": "2026-05-25",
            }
        ]
    }


def test_update_task_changes_matching_task() -> None:
    adapter = FakeNotionAdapter.from_initial_state(
        {
            "notion_tasks": [
                {
                    "id": "task_physics_lab_001",
                    "title": "Finish physics lab report",
                    "status": "open",
                    "due_date": "2026-05-22",
                }
            ]
        }
    )

    result = adapter.update_task(
        task_id="task_physics_lab_001",
        status="done",
    )

    tasks = adapter.export_state()["notion_tasks"]
    assert result.success is True
    assert result.tool == "notion.update_task"
    assert tasks[0]["title"] == "Finish physics lab report"
    assert tasks[0]["status"] == "done"
    assert tasks[0]["due_date"] == "2026-05-22"


def test_update_task_returns_failure_for_missing_task() -> None:
    adapter = FakeNotionAdapter.from_initial_state({"notion_tasks": []})

    result = adapter.update_task(
        task_id="task_missing_001",
        status="done",
    )

    assert result.success is False
    assert result.tool == "notion.update_task"
    assert result.error == "notion task not found: task_missing_001"
    assert adapter.export_state() == {"notion_tasks": []}


def test_update_task_rejects_invalid_title() -> None:
    adapter = FakeNotionAdapter.from_initial_state(
        {
            "notion_tasks": [
                {
                    "id": "task_physics_lab_001",
                    "title": "Finish physics lab report",
                    "status": "open",
                }
            ]
        }
    )

    with pytest.raises(ValidationError):
        adapter.update_task(
            task_id="task_physics_lab_001",
            title="",
        )


def test_create_task_generates_non_colliding_id() -> None:
    adapter = FakeNotionAdapter.from_initial_state(
        {
            "notion_tasks": [
                {
                    "id": "task_fake_notion_002",
                    "title": "Existing fake task",
                    "status": "open",
                }
            ]
        }
    )

    adapter.create_task(title="Submit scholarship form")

    tasks = adapter.export_state()["notion_tasks"]
    assert tasks[1]["id"] == "task_fake_notion_003"


def test_rejects_invalid_initial_notion_task() -> None:
    with pytest.raises(ValidationError):
        FakeNotionAdapter.from_initial_state(
            {
                "notion_tasks": [
                    {
                        "id": "task_bad_001",
                        "title": "",
                        "status": "open",
                    }
                ]
            }
        )
