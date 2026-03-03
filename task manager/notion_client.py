import os
import logging

from typing import Any, Dict

import requests

# simple wrapper for Notion API REST calls

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"  # keep consistent with Notion docs
NOTION_TIMEOUT = (5, 30)  # (connect timeout, read timeout)

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN environment variable not set")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def query_database(database_id: str, **kwargs: Any) -> Dict[str, Any]:
    url = f"{NOTION_API_BASE}/databases/{database_id}/query"
    res = requests.post(url, headers=_headers(), json=kwargs, timeout=NOTION_TIMEOUT)
    res.raise_for_status()
    return res.json()


def retrieve_page(page_id: str) -> Dict[str, Any]:
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    res = requests.get(url, headers=_headers(), timeout=NOTION_TIMEOUT)
    res.raise_for_status()
    return res.json()


def update_page(page_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    res = requests.patch(url, headers=_headers(), json=data, timeout=NOTION_TIMEOUT)
    res.raise_for_status()
    return res.json()


def create_page(parent_db: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{NOTION_API_BASE}/pages"
    payload = {"parent": {"database_id": parent_db}, "properties": properties}
    res = requests.post(url, headers=_headers(), json=payload, timeout=NOTION_TIMEOUT)
    res.raise_for_status()
    return res.json()


def create_database(parent_page_id: str, title: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new database under the given parent page.

    Returns the JSON response (which includes the new database's ID).
    """
    url = f"{NOTION_API_BASE}/databases"
    payload: Dict[str, Any] = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties,
    }
    res = requests.post(url, headers=_headers(), json=payload, timeout=NOTION_TIMEOUT)
    res.raise_for_status()
    return res.json()
