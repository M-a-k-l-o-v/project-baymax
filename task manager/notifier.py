"""Pluggable notification / alarm delivery for Baymax.

This module defines a very simple interface that the remainder of the
application can call when it wants to alert the user.  Concrete delivery
mechanisms (console, messaging apps, local alarms) live here, and the
caller doesn’t need to know which one is being used.

At startup the application can choose which channels to enable; the
default is just `ConsoleNotifier` which prints to stdout.  Later we can
easily add `EmailNotifier`, `TelegramNotifier`, etc.  A special
`AlarmNotifier` is responsible for telling the Mac to set a real
clock/alarm event.
"""
from __future__ import annotations

import datetime
import subprocess
import os
from typing import List, Optional

from .tasks import Task
from . import config


def _escape_applescript_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _configured_reminder_list() -> str:
    return os.environ.get("REMINDER_LIST") or config.get("reminder_list") or "Reminders"


def _task_marker(task_id: str) -> str:
    return f"[baymax:{task_id}]"


def reminder_title_for_task(task: Task) -> str:
    marker = _task_marker(task.id)
    if marker in task.title:
        return task.title
    return f"{task.title} {marker}"


def _reminder_due_date_str(due: Optional[datetime.datetime]) -> Optional[str]:
    if not isinstance(due, datetime.datetime):
        return None
    if due.tzinfo is not None and due.tzinfo.utcoffset(due) is not None:
        due = due.astimezone()
    # Format expected by AppleScript date parser.
    return due.strftime("%-m/%-d/%Y %I:%M:%S %p")


def ensure_task_reminder(task: Task, reminder_list: Optional[str] = None) -> bool:
    """Ensure a reminder exists for this task and keep title/due synced."""
    list_name = reminder_list or _configured_reminder_list()
    marker = _task_marker(task.id)
    reminder_name = reminder_title_for_task(task)
    due_str = _reminder_due_date_str(task.due)

    if due_str:
        script = (
            'tell application "Reminders"\n'
            'set theList to list "%s"\n'
            'set marker to "%s"\n'
            'set matches to every reminder of theList whose name contains marker\n'
            'if (count of matches) is 0 then\n'
            'make new reminder in theList with properties {name:"%s", due date:date "%s"}\n'
            'return "created"\n'
            'end if\n'
            'set r to item 1 of matches\n'
            'set name of r to "%s"\n'
            'set due date of r to date "%s"\n'
            'return "updated"\n'
            'end tell\n'
        ) % (
            _escape_applescript_text(list_name),
            _escape_applescript_text(marker),
            _escape_applescript_text(reminder_name),
            _escape_applescript_text(due_str),
            _escape_applescript_text(reminder_name),
            _escape_applescript_text(due_str),
        )
    else:
        script = (
            'tell application "Reminders"\n'
            'set theList to list "%s"\n'
            'set marker to "%s"\n'
            'set matches to every reminder of theList whose name contains marker\n'
            'if (count of matches) is 0 then\n'
            'make new reminder in theList with properties {name:"%s"}\n'
            'return "created"\n'
            'end if\n'
            'set r to item 1 of matches\n'
            'set name of r to "%s"\n'
            'return "updated"\n'
            'end tell\n'
        ) % (
            _escape_applescript_text(list_name),
            _escape_applescript_text(marker),
            _escape_applescript_text(reminder_name),
            _escape_applescript_text(reminder_name),
        )

    proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[AlarmNotifier] reminder ensure failed: rc={proc.returncode}")
        print(f"[AlarmNotifier] stderr: {proc.stderr}")
        return False
    return True


def get_task_reminder_completed(task: Task, reminder_list: Optional[str] = None) -> Optional[bool]:
    """Return reminder completion state for task or None if reminder is missing/error."""
    list_name = reminder_list or _configured_reminder_list()
    marker = _task_marker(task.id)
    script = (
        'tell application "Reminders"\n'
        'set theList to list "%s"\n'
        'set marker to "%s"\n'
        'set matches to every reminder of theList whose name contains marker\n'
        'if (count of matches) is 0 then return "missing"\n'
        'set r to item 1 of matches\n'
        'if completed of r then return "true"\n'
        'return "false"\n'
        'end tell\n'
    ) % (_escape_applescript_text(list_name), _escape_applescript_text(marker))
    proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[AlarmNotifier] reminder state lookup failed: rc={proc.returncode}")
        print(f"[AlarmNotifier] stderr: {proc.stderr}")
        return None
    state = proc.stdout.strip().lower()
    if state == "true":
        return True
    if state == "false":
        return False
    return None


def set_task_reminder_completed(task: Task, completed: bool, reminder_list: Optional[str] = None) -> bool:
    """Set completion on all reminders matching this task marker."""
    list_name = reminder_list or _configured_reminder_list()
    marker = _task_marker(task.id)
    completed_script = "true" if completed else "false"
    script = (
        'tell application "Reminders"\n'
        'set theList to list "%s"\n'
        'set marker to "%s"\n'
        'set matches to every reminder of theList whose name contains marker\n'
        'if (count of matches) is 0 then return "missing"\n'
        'repeat with r in matches\n'
        'set completed of r to %s\n'
        'end repeat\n'
        'return "ok"\n'
        'end tell\n'
    ) % (
        _escape_applescript_text(list_name),
        _escape_applescript_text(marker),
        completed_script,
    )
    proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[AlarmNotifier] reminder completion update failed: rc={proc.returncode}")
        print(f"[AlarmNotifier] stderr: {proc.stderr}")
        return False
    return proc.stdout.strip().lower() == "ok"


class Notifier:
    """Base class: subclasses implement delivery channels."""

    def notify(self, task: Task) -> None:
        """Deliver a reminder for `task`."""
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    def notify(self, task: Task) -> None:
        print(f"REMINDER: {task.title} due {task.due}")


class MessageNotifier(Notifier):
    """Send reminder via the Messages app (macOS only).

    This implementation uses `osascript` to send a message to a fixed
    recipient via Messages. The phone number or Apple ID should be 
    configured via the `MESSAGE_RECIPIENT` environment variable.

    """

    def __init__(self, recipient: str) -> None:
        self.recipient = recipient

    def notify(self, task: Task) -> None:
        text = f"{task.title} is due at {task.due}"
        
        # Escape special characters for AppleScript
        text_escaped = text.replace('"', '\\"')
        recipient_escaped = self.recipient.replace('"', '\\"')
        
        # Try to send via participant (more reliable than buddy)
        script = (
            f'tell application "Messages"\n'
            f'activate\n'
            f'set targetService to 1st service whose service type = iMessage\n'
            f'set targetBuddy to participant "{recipient_escaped}" of targetService\n'
            f'send "{text_escaped}" to targetBuddy\n'
            f'end tell'
        )
        
        print(f"[MessageNotifier] Sending to {self.recipient}: {text}")
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[MessageNotifier] send failed: rc={proc.returncode}")
            print(f"[MessageNotifier] stderr: {proc.stderr}")
            # Don't raise—at least log the attempt
        else:
            print(f"[MessageNotifier] message sent successfully")


class AlarmNotifier(Notifier):
    """Send an immediate local notification + audible alarm (macOS)."""

    def __init__(self, reminder_list: Optional[str] = None, alarm_rings: int = 5) -> None:
        self.reminder_list = reminder_list or _configured_reminder_list()
        self.alarm_rings = max(1, alarm_rings)

    def notify(self, task: Task) -> None:
        # Show native macOS notification immediately
        title = task.title
        subtitle = f"Due: {task.due}"

        # Escape special characters for AppleScript
        title_escaped = _escape_applescript_text(title)
        subtitle_escaped = _escape_applescript_text(subtitle)

        notification_script = (
            f'display notification "{subtitle_escaped}" with title "{title_escaped}"'
        )

        proc = subprocess.run(["osascript", "-e", notification_script], capture_output=True, text=True)
        if proc.returncode != 0:
            print("notification failed", proc.returncode, proc.stdout, proc.stderr)
            raise RuntimeError(f"notification failed: rc={proc.returncode} stderr={proc.stderr!r}")

        # Ring an audible alarm immediately when the task becomes due.
        ring_script = (
            f"repeat {self.alarm_rings} times\n"
            "beep\n"
            "delay 0.4\n"
            "end repeat"
        )
        proc = subprocess.run(["osascript", "-e", ring_script], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[AlarmNotifier] alarm ring failed: rc={proc.returncode}")
            print(f"[AlarmNotifier] stderr: {proc.stderr}")


# convenience helpers
_active_notifiers: List[Notifier] = [ConsoleNotifier()]


def configure(channels: List[str]) -> None:
    """Choose which notifiers should be active.

    `channels` is a list like ["console", "message", "alarm"].
    Environment variables such as MESSAGE_RECIPIENT are used for
    configuration.
    """
    global _active_notifiers
    notifiers: List[Notifier] = []
    for name in channels:
        if name == "console":
            notifiers.append(ConsoleNotifier())
        elif name == "message":
            # prefer explicit env var, fall back to persistent config
            recip = os.environ.get("MESSAGE_RECIPIENT") or config.get("message_recipient")
            if not recip:
                raise RuntimeError("MESSAGE_RECIPIENT not set (env or config)")
            notifiers.append(MessageNotifier(recip))
        elif name == "alarm":
            # prefer env var REMINDER_LIST, then config, then default
            reminder_list = os.environ.get("REMINDER_LIST") or config.get("reminder_list")
            rings_raw = os.environ.get("ALARM_RINGS") or config.get("alarm_rings") or 5
            try:
                rings = int(rings_raw)
            except (TypeError, ValueError):
                rings = 5
            notifiers.append(AlarmNotifier(reminder_list=reminder_list, alarm_rings=rings))
        else:
            raise ValueError(f"unknown notifier {name}")
    _active_notifiers = notifiers


def notify_all(task: Task) -> None:
    for n in _active_notifiers:
        name = n.__class__.__name__
        try:
            print(f"[notifier] calling {name} for task {task.id}")
            n.notify(task)
            print(f"[notifier] {name} succeeded")
        except Exception as e:
            # print full exception detail to help troubleshooting
            print(f"[notifier] {name} failed:", repr(e))
