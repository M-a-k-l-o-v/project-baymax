"""Minimal CLI for Baymax Notion-backed features."""

import argparse
import datetime
import os
import sys
import time

from . import tasks, reminders
from . import notifier
from . import config as baymax_config
from . import setup as setup_module
from . import watcher as watcher_module


def _default_notify_channels() -> list[str]:
    channels = ["console", "alarm"]
    if os.environ.get("MESSAGE_RECIPIENT") or baymax_config.get("message_recipient"):
        channels.append("message")
    return channels


def main():
    parser = argparse.ArgumentParser(prog="baymax")
    sub = parser.add_subparsers(dest="command")

    tlist = sub.add_parser("list-tasks")
    tlist.add_argument("--db", required=True, help="Notion database ID")

    tcreate = sub.add_parser("create-task")
    tcreate.add_argument("--db", required=True, help="Notion database ID")
    tcreate.add_argument("title", help="Task title")
    tcreate.add_argument("--due", help="ISO due date/time")

    remind = sub.add_parser("start-reminders")
    remind.add_argument("--db", required=True, help="Notion database ID")
    remind.add_argument("--interval", type=float, default=60.0)
    remind.add_argument("--notify-channels",
                        help="comma-separated list of notifier names (console,message,alarm)")
    remind.add_argument("--watch-interval", type=float, default=15.0,
                        help="seconds between DB-change checks")
    remind.add_argument("--no-db-watch", action="store_true",
                        help="disable DB change monitor")

    test_notifier = sub.add_parser("test-notifier")
    test_notifier.add_argument("--notify-channels",
                               help="comma-separated list of notifier names (console,message,alarm)")

    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd")

    cfg_set = cfg_sub.add_parser("set")
    cfg_set.add_argument("key", help="config key to set (eg: message_recipient, notification_channels)")
    cfg_set.add_argument("value", help="value to store")

    cfg_show = cfg_sub.add_parser("show")
    cfg_show.add_argument("--raw", action="store_true", help="Print raw JSON config")

    setup = sub.add_parser("setup-db")
    setup.add_argument("--parent", required=True,
                       help="Notion page ID under which to create the database")
    setup.add_argument("--name", default="Tasks", help="Name of the new database")

    changepoint = sub.add_parser("changepoint-check")
    changepoint.add_argument("--db", required=True, help="Notion database ID")
    changepoint.add_argument("--state-file",
                             help="path to watcher state file for cron mode")
    changepoint.add_argument("--notify-channels",
                             help="comma-separated list of notifier names (console,message,alarm)")

    args = parser.parse_args()

    if args.command == "list-tasks":
        ts = tasks.list_tasks(args.db)
        for t in ts:
            print(t)
    elif args.command == "create-task":
        due = None
        if args.due:
            due = datetime.datetime.fromisoformat(args.due)
        t = tasks.create_task(args.db, args.title, due=due)
        try:
            notifier.ensure_task_reminder(t)
        except Exception as e:
            print(f"[create-task] reminder registration failed: {e}")
        print("Created", t)
    elif args.command == "start-reminders":
        # determine channels: CLI flag > env var > persistent config
        channels_val = None
        if args.notify_channels:
            channels_val = args.notify_channels
        else:
            channels_val = os.environ.get("NOTIFICATION_CHANNELS") or baymax_config.get("notification_channels")
        if channels_val:
            channels = [c.strip() for c in channels_val.split(",") if c.strip()]
            notifier.configure(channels)
        else:
            notifier.configure(_default_notify_channels())
        svc = reminders.ReminderService(args.db, check_interval=args.interval)
        db_watcher = None

        def on_rem(task):
            print(f"REMINDER: {task.title} due {task.due}")

        svc.on_reminder = on_rem
        if not args.no_db_watch:
            def on_db_change(_tasks):
                print("[watcher] Notion DB changed; forcing immediate reminder recheck")
                svc.request_recheck()

            db_watcher = watcher_module.ChangeWatcher(
                args.db,
                interval=args.watch_interval,
                on_change=on_db_change,
            )

        print("starting reminder service; ctrl-c to stop")
        if db_watcher:
            print(f"starting DB change monitor (interval={args.watch_interval}s)")
        try:
            svc.start()
            if db_watcher:
                db_watcher.start_background()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            svc.stop()
            if db_watcher:
                db_watcher.stop()
    elif args.command == "config":
        if args.cfg_cmd == "set":
            # store as string; for channels expect comma-separated
            baymax_config.set(args.key, args.value)
            print(f"saved {args.key}")
        elif args.cfg_cmd == "show":
            # print entire config
            cfg = baymax_config.load()
            if args.raw:
                import json

                print(json.dumps(cfg, indent=2, ensure_ascii=False))
            else:
                for k, v in cfg.items():
                    print(f"{k}: {v}")
    elif args.command == "test-notifier":
        # Run an internal notifier test: configure channels and send a fake task
        # This is a convenience helper so you don't need to create temp files.
        channels_val = None
        if args.notify_channels:
            channels_val = args.notify_channels
        else:
            channels_val = os.environ.get("NOTIFICATION_CHANNELS") or baymax_config.get("notification_channels")
        if channels_val:
            channels = [c.strip() for c in channels_val.split(",") if c.strip()]
            notifier.configure(channels)
        else:
            notifier.configure(_default_notify_channels())

        # create and send a fake Task due now
        due = datetime.datetime.now()
        fake = tasks.Task("test-1", "Baymax notifier test", due=due)
        print("Sending test notification for:", fake)
        notifier.notify_all(fake)
    elif args.command == "setup-db":
        # create a Tasks database under the given parent page
        db_id = setup_module.create_tasks_database(args.parent, title=args.name)
        print(f"Created database with ID {db_id}")
    elif args.command == "changepoint-check":
        # one-shot DB changepoint check for cron jobs
        channels_val = None
        if args.notify_channels:
            channels_val = args.notify_channels
        else:
            channels_val = os.environ.get("NOTIFICATION_CHANNELS") or baymax_config.get("notification_channels")
        if channels_val:
            channels = [c.strip() for c in channels_val.split(",") if c.strip()]
            notifier.configure(channels)
        else:
            notifier.configure(_default_notify_channels())

        svc = reminders.ReminderService(args.db, check_interval=60.0)
        changed = watcher_module.changepoint_check(
            args.db,
            state_file=args.state_file,
            on_change=svc.check_once,
        )
        if changed:
            print("Notion DB changed; reminder recheck executed")
        else:
            print("No Notion DB changes detected")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
