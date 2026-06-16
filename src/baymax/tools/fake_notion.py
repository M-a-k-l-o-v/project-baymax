"""Fake Notion adapter for deterministic eval runs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from baymax.tools.fake_base import FakeToolResult

TaskStatus = Literal["open", "done"]


class NotionTask(BaseModel):
    """Notion task stored in the fake adapter state."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = Field(min_length=1)
    status: TaskStatus = "open"
    due_date: str | None = None


class FakeNotionAdapter:
    """In-memory Notion adapter backed by scenario state."""

    def __init__(self, tasks: list[NotionTask] | None = None) -> None:
        self._tasks = list(tasks or [])

    @classmethod
    def from_initial_state(cls, initial_state: dict[str, Any]) -> FakeNotionAdapter:
        raw_tasks = initial_state.get("notion_tasks", [])
        tasks = [NotionTask.model_validate(task) for task in raw_tasks]
        return cls(tasks=tasks)

    def export_state(self) -> dict[str, Any]:
        return {
            "notion_tasks": [
                task.model_dump(mode="json", exclude_none=True) for task in self._tasks
            ]
        }

    def create_task(
        self,
        *,
        title: str,
        due_date: str | None = None,
        status: TaskStatus = "open",
    ) -> FakeToolResult:
        task = NotionTask(
            id=self._next_task_id(),
            title=title,
            due_date=due_date,
            status=status,
        )
        self._tasks.append(task)
        return FakeToolResult(
            success=True,
            tool="notion.create_task",
            data={"task_id": task.id},
        )

    def update_task(
        self,
        *,
        task_id: str,
        title: str | None = None,
        status: TaskStatus | None = None,
        due_date: str | None = None,
    ) -> FakeToolResult:
        task_index = self._find_task_index(task_id)
        if task_index is None:
            return FakeToolResult(
                success=False,
                tool="notion.update_task",
                error=f"notion task not found: {task_id}",
            )

        existing_task = self._tasks[task_index]
        self._tasks[task_index] = NotionTask.model_validate(
            {
                **existing_task.model_dump(mode="json"),
                **{
                    key: value
                    for key, value in {
                        "title": title,
                        "status": status,
                        "due_date": due_date,
                    }.items()
                    if value is not None
                },
            }
        )
        return FakeToolResult(success=True, tool="notion.update_task")

    def _find_task_index(self, task_id: str) -> int | None:
        for index, task in enumerate(self._tasks):
            if task.id == task_id:
                return index
        return None

    def _next_task_id(self) -> str:
        existing_ids = {task.id for task in self._tasks}
        next_index = len(self._tasks) + 1
        while True:
            candidate_id = f"task_fake_notion_{next_index:03}"
            if candidate_id not in existing_ids:
                return candidate_id
            next_index += 1
