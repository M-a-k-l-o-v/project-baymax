from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from .notion_client import query_database, create_page, update_page


def _as_utc(dt: datetime.datetime) -> datetime.datetime:
    """Return a timezone-aware UTC datetime."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


@dataclass
class Task:
    id: str
    title: str
    due: Optional[datetime.datetime] = None
    status: str = "Not Started"
    priority: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_notion(cls, page: dict) -> "Task":
        props = page.get("properties", {})
        title = ""
        if "Name" in props and props["Name"].get("title"):
            title = props["Name"]["title"][0].get("plain_text", "")
        due = None
        if "Due" in props and props["Due"].get("date"):
            due = _as_utc(datetime.datetime.fromisoformat(props["Due"]["date"]["start"]))
        status = ""
        if "Status" in props and isinstance(props["Status"], dict) and props["Status"].get("select"):
            status = props["Status"]["select"].get("name", "")
        priority = None
        if "Priority" in props and isinstance(props["Priority"], dict) and props["Priority"].get("select"):
            priority = props["Priority"]["select"].get("name")
        tags = []
        if "Tags" in props and props["Tags"].get("multi_select"):
            tags = [t["name"] for t in props["Tags"]["multi_select"]]
        return cls(page["id"], title, due, status, priority, tags)


def list_tasks(database_id: str) -> List[Task]:
    results = []
    resp = query_database(database_id)
    for page in resp.get("results", []):
        results.append(Task.from_notion(page))
    return results


def create_task(database_id: str, title: str, due: Optional[datetime.datetime] = None,
                priority: Optional[str] = None) -> Task:
    props: dict = {
        "Name": {"title": [{"text": {"content": title}}]}
    }
    if due:
        props["Due"] = {"date": {"start": _as_utc(due).isoformat()}}
    if priority:
        props["Priority"] = {"select": {"name": priority}}
    page = create_page(database_id, props)
    return Task.from_notion(page)


def update_task(task: Task, **changes) -> Task:
    props = {}
    if "title" in changes:
        props["Name"] = {"title": [{"text": {"content": changes["title"]}}]}
    if "due" in changes:
        val = changes["due"]
        if isinstance(val, datetime.datetime):
            val = _as_utc(val).isoformat()
        props["Due"] = {"date": {"start": val}}
    if "status" in changes:
        props["Status"] = {"select": {"name": changes["status"]}}
    if "priority" in changes:
        props["Priority"] = {"select": {"name": changes["priority"]}}
    page = update_page(task.id, {"properties": props})
    return Task.from_notion(page)
