# BAYMAX Project

This workspace contains the BAYMAX project and related utilities. The main purpose is to build a personal assistant named **Baymax** with features backed by Notion, such as to-do lists, reminders, financial tracking, etc.

## Notion-backed To-do MVP

A minimal Python package under `baymax/` provides:

- `notion_client.py` – lightweight wrapper around Notion REST API
- `tasks.py` – simple dataclass and helpers for reading/creating/updating tasks
- `reminders.py` – poll-based reminder service that fires callbacks when tasks are due
- `cli.py` – command‑line interface for experimenting with the system

!! - the notion thing might set up as an extention in the future not the main db, so you could connect the assisstant to notion or your prefered noting platform

### Getting started

1. Create and activate a Python virtual environment in the repo root:
   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install -U pip requests
   pip install notion-client
   ```

2. Set your Notion integration token:
   ```sh
   export NOTION_TOKEN="secret_xxx"
   ```

3. Use the CLI:
   ```sh
   python -m baymax.cli list-tasks --db <DATABASE_ID>
   python -m baymax.cli create-task --db <DATABASE_ID> "Buy milk" --due "2026-03-02T09:00:00"
   python -m baymax.cli start-reminders --db <DATABASE_ID>
   ```

   *Optionally*, you can create the `Tasks` database from code rather than by hand. The helper uses the same API that the Notion UI uses:
   ```sh
   python -m baymax.cli setup-db --parent <PARENT_PAGE_ID> --name "Tasks"
   ```
   (`<PARENT_PAGE_ID>` must be the ID of an existing Notion **page**; you cannot use a database ID.)
   It prints the new database ID, which you can then supply to the other commands.

The code above constitutes an MVP that should take 1–2 days to build as described. Future enhancements can add filtering, tagging, webhook support, and notification delivery via various channels.

### Notes added during setup

* `baymax.cli` now includes a `setup-db` command for creating the default Tasks database programmatically; use a page ID as the parent and the command will print the resulting database ID. This is handy for reproducible environments and tests.
* A helper module (`baymax.setup`) contains the schema and a `create_tasks_database()` function so scripts or unit tests can bootstrap clean databases.

### Next steps (coming up)

1. **Notification delivery** – wire the reminder service to send out messages (email, Discord, Telegram, etc.) instead of printing to stdout.  We now have a `baymax.notifier` module with a pluggable API; you can configure channels such as `console`, `message`, and `alarm`.

   Example CLI usage to start reminders with console + alarm notifications:
   ```sh
   # set channels and optional message recipient before starting (or persist with `baymax config`)
   export NOTIFICATION_CHANNELS=console,alarm
   export MESSAGE_RECIPIENT="+15551234567"   # only needed if channel includes 'message'
   python -m baymax.cli start-reminders --db <DATABASE_ID> --notify-channels console,alarm
   ```
   Persist instead of exporting every session:
   ```sh
   # store the default channels and message recipient in persistent config
   python -m baymax.cli config set notification_channels console,alarm
   python -m baymax.cli config set message_recipient marvellousolushola@icloud.com
   # then you can simply start reminders without exporting
   python -m baymax.cli start-reminders --db <DATABASE_ID>
   ```
   In Python you can set it up directly:
   ```python
   from baymax import notifier
   notifier.configure(["console", "alarm"])
   ```
   *`MESSAGE_RECIPIENT`* environment variable must be set if you include
   the `message` channel; it should be an iMessage address or phone number.

2. **MacBook alarm integration** – the `AlarmNotifier` currently creates
   a Calendar event with a display alarm using AppleScript (see
   `baymax/notifier.py`). This is a pragmatic way to get a real alert on
   macOS without building a separate app; later we can try driving the
   Clock app directly or use an Apple Shortcut if more control is needed.
   The example AppleScript is simple and may need tweaking for your
   setup, but it shows the pattern: convert the due time to an ISO string
   and `osascript` a small script that makes an event and adds an alarm.
