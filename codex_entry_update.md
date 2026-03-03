# Codex Entry: BAYMAX Notion-Backed MVP Architecture

**Date:** March 1, 2026  
**Status:** MVP Foundation Laid  
**Scope:** Tasks + Reminders MVP (Notion-backed, polling-based)

---

## Overview

This update introduces the **foundational architecture** for BAYMAX, a multi-agent personal assistant system. The initial MVP focuses on:

- **To-do list** backed by Notion (read, create, update tasks)
- **Reminder service** that polls tasks and fires callbacks when due dates pass
- **Lightweight CLI** for manual interaction and testing

The design intentionally stays minimal—this is a 1–2 day build as scoped. All code follows the **shared data layer + tool layer + agent-module** pattern described in the long-term roadmap, so future enhancements (webhooks, notifications, finance tracking, vision) will slot in cleanly without rearchitecting.

---

## What Was Added

### 1. **`baymax/` Package**

A new Python package containing all Baymax-specific logic, organized by concern:

#### `baymax/notion_client.py`
**Purpose:** Thin REST wrapper around the Notion API.

**Key functions:**
- `query_database(database_id, **kwargs)` – POST to `/databases/{id}/query` with filters/sorts
- `retrieve_page(page_id)` – GET a single page  
- `update_page(page_id, data)` – PATCH page properties
- `create_page(parent_db, properties)` – POST a new page to a database

**Why:** Isolates authentication (token from `NOTION_TOKEN` env var) and API version in one place. Makes it trivial to add new Notion operations later without repeating boilerplate.

---

#### `baymax/tasks.py`
**Purpose:** Business logic for to-do lists.

**Key components:**

- **`Task` dataclass**  
  Represents a single task with fields:
  - `id` – Notion page ID (needed for updates)
  - `title` – task name
  - `due` – optional datetime
  - `status` – select (e.g., "Not Started", "In Progress", "Done")
  - `priority` – optional select
  - `tags` – multi-select list

- **`Task.from_notion(page)`** – Constructor that parses a Notion page's properties JSON into a `Task` object. Handles field extraction safely (properties are nested; dates are ISO strings).

- **`list_tasks(database_id)`** – Fetch all tasks from a database.

- **`create_task(database_id, title, due=None, priority=None)`** – Create a new task in Notion.

- **`update_task(task, **changes)`** – Update a task's title, due date, status, or priority.

**Why:** Decouples Notion's property schema from application code. A single `Task` object is cleaner than passing around raw Notion JSON. Easy to add validation, computed fields, or caching later.

---

#### `baymax/reminders.py`
**Purpose:** A simple reminder service that monitors task due dates.

**Key components:**

- **`ReminderService` class**  
  - Runs in a background thread (daemon mode, no blocking)
  - Polls the task database every `check_interval` seconds  
  - Tracks which tasks have already fired a reminder (deduplication via `_last_seen` dict)
  - Calls a user-provided callback `on_reminder(task)` when a task's due date has passed

**How it works:**
  1. Polling loop iterates tasks continuously
  2. For each task with a due date ≤ now, check if we've seen it before
  3. If it's new or due date was updated, fire the callback and record the timestamp
  4. Sleep for `check_interval`, then repeat

**Why:** Polling is the simplest approach for an MVP. No webhook complexity, just a small overhead. Later you'll upgrade to webhooks (Notion pushes events to you) and a scheduler with cron-like syntax. The service is designed to persist across multiple polls, so reminders don't fire repeatedly.

---

#### `baymax/cli.py`
**Purpose:** Command-line interface for experimenting with the above modules.

**Commands:**
- `baymax list-tasks --db <ID>` – Print all tasks
- `baymax create-task --db <ID> "Title" [--due "2026-03-02T09:00:00"]` – Add a task
- `baymax start-reminders --db <ID> [--interval 60.0]` – Run reminder service (foreground, Ctrl-C to stop)

**Why:** Provides a quick way to test without writing Python code. CLI is also a natural "tool interface" that agents will eventually call to access tasks.

---

### 2. **Updated `README.md`**

Added getting-started instructions:
- Virtual env setup
- Notion integration token setup
- Example CLI usage
- Pointers to next steps (webhooks, notifications, finance, vision)

---

## Design Principles

### 1. **Shared Data Layer**
All agents will eventually read/write the same `Task` model and database. No duplicated state.

### 2. **Tool Layer**
Each capability (Notion queries, notifications, calendar events, camera, etc.) is a self-contained module. Agents call tools, not each other directly.

### 3. **Polling → Webhooks → Smarter Scheduling**
- **Today:** Simple polling loop, deduplicated callbacks.
- **Week 2–3:** Notion webhooks push "something changed" signals; fetch updated data on demand.
- **Later:** Cron-like scheduling so Baymax can proactively run agents (e.g., "check finances every Friday").

### 4. **Extensibility**
- Add a new Notion table (e.g., Transactions, Clips) → add a new `<feature>.py` module with the same pattern.
- Add a new notification channel → plug in a `notifier` module with `send_email()`, `send_discord()`, etc.
- Add vision → import `yolo_model` and call it from a `VisionAgent`.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    BAYMAX (Multi-Agent)                      │
├──────────────────────────┬──────────────────────────────────┤
│  TaskAgent               │  ReminderAgent | FinanceAgent    │
│  (uses Task tool)        │  (uses Reminder + Notif tools)   │
└──────────────────────────┴──────────────────────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │      Orchestrator / Scheduler         │
         │  (routes requests, runs agents)       │
         └──────────────────────────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │           Tool Layer                  │
         │  ┌──────────────────────────────────┐ │
         │  │ • tasks.py  (Task CRUD)          │ │
         │  │ • reminders.py  (polling svc)    │ │
         │  │ • notifier.py  (email/Discord)   │ │
         │  │ • finance.py   (transactions)    │ │
         │  │ • vision.py    (YOLO inference)  │ │
         │  └──────────────────────────────────┘ │
         └──────────────────────────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │    Shared Data Layer (SQLite + Sync) │
         │  ┌──────────────────────────────────┐ │
         │  │  Tasks | Finance | Clips | etc. │ │
         │  └──────────────────────────────────┘ │
         └──────────────────────────────────────┘
                            ↓
         ┌──────────────────────────────────────┐
         │    Notion (optional, live sync)       │
         │  (Tasks DB, Finance DB, Clips DB)     │
         └──────────────────────────────────────┘
```

---

## Quick Start

### 1. Environment Setup

```bash
cd /Users/yin/Documents/projects/Programming/BAYMAX

# Create and activate venv
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -U pip requests notion-client
```

### 2. Notion Setup

1. Go to [notion.so](https://notion.so)
2. Create an integration at [https://www.notion.com/my-integrations](https://www.notion.com/my-integrations)
3. Copy the integration token and save it:
   ```bash
   export NOTION_TOKEN="secret_xxx..."
   ```
4. Create a database called "Tasks" with properties:
   - `Name` (title)
   - `Due` (date)
   - `Status` (select: "Not Started", "In Progress", "Done")
   - `Priority` (select: "Low", "Medium", "High")
   - `Tags` (multi-select)
5. Copy the database ID from the URL and use it below

### 3. Test the MVP

```bash
# Set token first
export NOTION_TOKEN="secret_xxx..."
DB="<your-database-id>"

# List existing tasks
python -m baymax.cli list-tasks --db $DB

# Create a task
python -m baymax.cli create-task --db $DB "Review Baymax code" --due "2026-03-03T14:00:00"

# Start the reminder service (will print to stdout when tasks are due)
python -m baymax.cli start-reminders --db $DB --interval 10
```

---

## What's NOT Included (Phase 2+)

- ❌ **Webhooks** – Notion can push changes if you set up a webhook endpoint  
- ❌ **Notifications** – Email, SMS, Telegram, Discord integrations  
- ❌ **Recurring tasks** – e.g., "every Monday at 9 AM"  
- ❌ **Filtering/tagging** – "show me overdue", "show me high priority"  
- ❌ **Finance tracker** – Transaction database + summaries  
- ❌ **Clipit** – Snippet/link saver with tagging  
- ❌ **Vision** – Object recognition via YOLO or similar  
- ❌ **Calendar sync** – Google Calendar / Apple Calendar exports  
- ❌ **Phone integration** – Alarm app bridging (complex, platform-specific)

These will follow the same **tool + agent** pattern once scoped.

---

## Performance & Scalability Notes

### Polling overhead
- Default 60-second interval = ~1 API call/minute
- Notion's free plan allows 3 requests/second, so no issues
- Deduplication prevents duplicate notifications even if you have many tasks

### On M1 Pro / 16 GB
- This MVP uses negligible CPU/memory
- SQLite caching (coming soon) will reduce API calls further
- Vision inference on-demand only; won't impact basics

### Future: Webhooks
- Replace polling with event-driven architecture
- Baymax wakes up only when Notion sends a webhook (task created/updated)
- Drastically reduces API usage + latency

---

## Next Steps (Recommended Priority)

1. **Phone notifications** (2–3 days)
   - Add a `notifier.py` module
   - Integrate email / Discord / Telegram
   - Have `ReminderService` call `notifier.send()` instead of printing

2. **Webhook support** (3–5 days)
   - Set up a simple HTTP endpoint that Notion can POST to
   - Replace polling with event-driven updates
   - Deduplication still applies

3. **Finance tracker MVP** (2–5 days)
   - Add `finance.py` with `Transaction` dataclass
   - Notion "Transactions" table (amount, category, date, merchant)
   - CLI to list / create transactions

4. **Clipit MVP** (1–3 days)
   - Add `clips.py` with `Clip` dataclass
   - Notion "Clips" table (url, tags, notes, source)
   - CLI to save / list clips

5. **Multi-agent orchestrator** (ongoing)
   - Create `orchestrator.py` that routes requests
   - Each agent (TaskAgent, ReminderAgent, etc.) is a small module
   - Orchestrator schedules agents and merges results

---

## Code Quality & Testing

**Current status:** Minimal, working MVP code.

**Future improvements:**
- Unit tests for `Task.from_notion()`, `Task` updates
- Integration tests against a test Notion database
- Error handling (network timeouts, Notion API errors)
- Logging instead of print()
- Type hints (partially done; can be completed)

---

## Summary

**What you have now:**
- A clean, extensible foundation for a personal assistant
- Notion-backed to-do list with CRUD
- Simple polling-based reminders
- CLI for testing and manual interaction
- Clear path to add agents, webhooks, notifications, and more

**Why this approach:**
- Avoids over-engineering (MVP = 1–2 days)
- Respects the "shared data + tool layer + agents" architecture from day 1
- Minimal dependencies (requests + notion-client, both lightweight)
- Scales from laptop polling all the way to a distributed system with webhooks

**Estimated total time to "polished MVP"** (tasks + reminders + notifications + webhooks):  
**7–14 days** at 2–3 hours/day, or 2–3 solid days full-time.

---

**Next move:** Pick which feature to harden first (notifications? webhooks? finance?) and keep the momentum going.
