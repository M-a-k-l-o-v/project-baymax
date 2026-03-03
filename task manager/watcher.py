"""DB change watcher for Baymax.

Polls a Notion database via `tasks.list_tasks()` and computes a
fingerprint. When the fingerprint changes it calls `on_change(new_tasks)`.

This is intentionally simple (polling) so it can be run as a cron job or
as a long-running process.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Dict, List, Optional

from .tasks import Task, list_tasks


def _fingerprint(tasks: List[Task]) -> str:
    # Create a stable JSON representation of tasks for hashing
    serial = []
    for t in sorted(tasks, key=lambda x: x.id):
        serial.append({
            "id": t.id,
            "title": t.title,
            "due": str(t.due),
            "status": t.status,
            "priority": t.priority,
            "tags": list(t.tags) if getattr(t, "tags", None) is not None else [],
        })
    data = json.dumps(serial, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class ChangeWatcher:
    """Poll a Notion DB and call `on_change` when items change.

    Args:
        db_id: Notion database id
        interval: polling interval in seconds
        on_change: callback called with new task list when change detected
    """

    def __init__(self, db_id: str, interval: float = 60.0, on_change: Optional[Callable[[List[Task]], None]] = None):
        self.db_id = db_id
        self.interval = interval
        self.on_change = on_change
        self._running = False
        self._last_fp: Optional[str] = None
        self._stop_event = threading.Event()

    def poll_once(self) -> bool:
        """Poll the DB once, returning True if a change is detected."""
        tasks = list_tasks(self.db_id)
        fp = _fingerprint(tasks)
        if self._last_fp is None:
            self._last_fp = fp
            return False
        if fp != self._last_fp:
            self._last_fp = fp
            if self.on_change:
                try:
                    self.on_change(tasks)
                except Exception as e:
                    print("ChangeWatcher callback error", e)
            return True
        return False

    def start(self):
        self._running = True
        self._stop_event.clear()
        while self._running and not self._stop_event.is_set():
            try:
                self.poll_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("ChangeWatcher error", e)
            self._stop_event.wait(self.interval)

    def start_background(self) -> threading.Thread:
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._running = False
        self._stop_event.set()


def _default_state_file() -> Path:
    return Path(os.path.expanduser("~")) / ".baymax" / "watcher_state.json"


def _load_state_fingerprint(state_file: Path) -> Optional[str]:
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    fp = data.get("fingerprint")
    if isinstance(fp, str):
        return fp
    return None


def _save_state_fingerprint(state_file: Path, fingerprint: str) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprint": fingerprint}
    state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def changepoint_check(
    db_id: str,
    state_file: Optional[str] = None,
    on_change: Optional[Callable[[List[Task]], None]] = None,
) -> bool:
    """Single poll intended for cron: returns True only when DB changed."""
    tasks = list_tasks(db_id)
    current_fp = _fingerprint(tasks)
    state_path = Path(state_file) if state_file else _default_state_file()
    previous_fp = _load_state_fingerprint(state_path)
    changed = previous_fp is not None and previous_fp != current_fp
    _save_state_fingerprint(state_path, current_fp)
    if changed and on_change:
        try:
            on_change(tasks)
        except Exception as e:
            print("changepoint_check callback error", e)
    return changed
