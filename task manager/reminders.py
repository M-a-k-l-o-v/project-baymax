import datetime
import threading
from typing import Callable, List, Optional

from .tasks import list_tasks, Task, update_task
from . import notifier


def _as_utc(dt: datetime.datetime) -> datetime.datetime:
    """Return a timezone-aware UTC datetime."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _is_done_status(status: Optional[str]) -> bool:
    if not status:
        return False
    return status.strip().lower() in {"done", "completed", "complete", "finished"}


class ReminderService:
    def __init__(self, database_id: str, check_interval: float = 60.0):
        self.database_id = database_id
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._last_seen: dict[str, datetime.datetime] = {}
        self._reminder_signature: dict[str, tuple[str, Optional[datetime.datetime]]] = {}
        self.on_reminder: Optional[Callable[[Task], None]] = None

    def start(self):
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()

    def request_recheck(self):
        """Trigger an immediate recheck outside the regular interval."""
        self._wake_event.set()

    def check_once(self, tasks: Optional[List[Task]] = None):
        if tasks is None:
            tasks = list_tasks(self.database_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        for t in tasks:
            due_sig = _as_utc(t.due) if t.due else None
            sig = (t.title, due_sig)

            if _is_done_status(t.status):
                reminder_completed = notifier.get_task_reminder_completed(t)
                if reminder_completed is False:
                    notifier.set_task_reminder_completed(t, completed=True)
                continue

            if self._reminder_signature.get(t.id) != sig:
                if notifier.ensure_task_reminder(t):
                    self._reminder_signature[t.id] = sig

            reminder_completed = notifier.get_task_reminder_completed(t)
            if reminder_completed:
                try:
                    updated = update_task(t, status="Done")
                    t.status = updated.status
                    print(f"[reminders] synced completion from Reminders -> Notion for task {t.id}")
                except Exception as e:
                    print(f"[reminders] failed syncing completion to Notion for task {t.id}: {e}")
                continue

            if t.due:
                due = _as_utc(t.due)
                # simple reminder when due time passed
                if due <= now:
                    last = self._last_seen.get(t.id)
                    if not last or last < due:
                        self._last_seen[t.id] = due
                        t.due = due
                        if self.on_reminder:
                            self.on_reminder(t)
                        # also send notifications via configured notifiers
                        notifier.notify_all(t)

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self.check_once()
            except Exception as e:
                print("ReminderService error", e)
            self._wake_event.wait(self.check_interval)
            self._wake_event.clear()
