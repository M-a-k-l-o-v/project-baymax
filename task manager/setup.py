"""Convenience helpers for creating Notion databases used by Baymax."""
from typing import Dict

from .notion_client import create_database


def tasks_database_schema() -> Dict[str, Dict]:
    """Return the property schema for the default Tasks database."""
    return {
        "Name": {"title": {}},
        "Due": {"date": {}},
        "Status": {
            "select": {
                "options": [
                    {"name": "Not Started", "color": "default"},
                    {"name": "In Progress", "color": "yellow"},
                    {"name": "Done", "color": "green"},
                ]
            }
        },
        "Priority": {
            "select": {
                "options": [
                    {"name": "Low", "color": "blue"},
                    {"name": "Medium", "color": "orange"},
                    {"name": "High", "color": "red"},
                ]
            }
        },
        "Tags": {"multi_select": {"options": []}},
    }


def create_tasks_database(parent_page_id: str, title: str = "Tasks") -> str:
    """Create a new Tasks database under the given parent page.

    Returns the database ID string.
    """
    resp = create_database(parent_page_id, title, tasks_database_schema())
    return resp["id"]
