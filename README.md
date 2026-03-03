# BAYMAX

Last updated: March 3, 2026

## What BAYMAX Currently Is

BAYMAX is currently a multi-project workspace with three active prototypes:

1. A Notion-backed task/reminder automation stack (`task manager/`)
2. A voice assistant experiment using speech recognition + local LLMs (`voice Interactive chat bot/`)
3. A manual webcam-to-3D reconstruction experiment (`Virtual_space_constructor/`)

This repository is not yet a single polished product. It is a working R&D workspace with multiple modules at different maturity levels.

## Workspace Layout

```text
BAYMAX/
├── README.md
├── baymax architecture planning.md
├── clipThat.py
├── task manager/
│   ├── cli.py
│   ├── notion_client.py
│   ├── tasks.py
│   ├── reminders.py
│   ├── notifier.py
│   ├── watcher.py
│   ├── setup.py
│   └── config.py
├── voice Interactive chat bot/
│   ├── main.py
│   ├── Prompt_input.py
│   ├── Reasoning.py
│   ├── API_and_tools.py
│   └── README.md
└── Virtual_space_constructor/
    ├── Main.py
    ├── live_3d_reconstructor.py
    ├── Readme
    └── scanned_scene.ply
```

## 1) Notion Task + Reminder Stack (`task manager/`)

### Current Capabilities

1. Notion REST API wrapper for:
   - Querying databases
   - Retrieving pages
   - Updating pages
   - Creating pages
   - Creating databases
2. Typed `Task` model (`id`, `title`, `due`, `status`, `priority`, `tags`)
3. Task CRUD-style helpers:
   - List tasks from Notion
   - Create task
   - Update task fields
4. Reminder polling service:
   - Periodic due-date checks
   - Immediate recheck trigger
   - Deduped reminder firing
5. Reminder/notification channels:
   - Console prints
   - macOS Messages (iMessage via AppleScript)
   - macOS local notification + audible beeps
6. Apple Reminders sync behaviors:
   - Create/update reminders for Notion tasks
   - Read reminder completion state
   - Mark reminder completion state from code
   - Push completion back to Notion (`Status="Done"`)
7. Database change watcher:
   - Long-running polling mode
   - One-shot changepoint mode for cron jobs
8. Persistent local config:
   - Stored at `~/.baymax/config.json`
9. Notion Tasks DB bootstrap helper:
   - Creates expected schema under a parent page

### CLI Commands Implemented

From `task manager/cli.py`, the command surface currently includes:

1. `list-tasks --db <DATABASE_ID>`
2. `create-task --db <DATABASE_ID> <TITLE> [--due <ISO_DATETIME>]`
3. `start-reminders --db <DATABASE_ID> [--interval <SECONDS>] [--notify-channels ...] [--watch-interval ...] [--no-db-watch]`
4. `test-notifier [--notify-channels ...]`
5. `config set <KEY> <VALUE>`
6. `config show [--raw]`
7. `setup-db --parent <PARENT_PAGE_ID> [--name <DB_NAME>]`
8. `changepoint-check --db <DATABASE_ID> [--state-file <PATH>] [--notify-channels ...]`

### Expected Notion Database Schema

Default schema created by `setup.py`:

1. `Name` (title)
2. `Due` (date)
3. `Status` (select: `Not Started`, `In Progress`, `Done`)
4. `Priority` (select: `Low`, `Medium`, `High`)
5. `Tags` (multi-select)

### Environment Variables and Config

Environment variables used:

1. `NOTION_TOKEN` (required for Notion API calls)
2. `NOTIFICATION_CHANNELS` (optional, comma-separated)
3. `MESSAGE_RECIPIENT` (required if `message` channel is enabled)
4. `REMINDER_LIST` (optional, Apple Reminders list name)
5. `ALARM_RINGS` (optional, number of beep cycles)

Persistent config keys (in `~/.baymax/config.json`) commonly used:

1. `message_recipient`
2. `notification_channels`
3. `reminder_list`
4. `alarm_rings`

### macOS Dependencies

`notifier.py` uses `osascript`, so macOS is currently required for:

1. Messages channel (`MessageNotifier`)
2. Local alarm/notification channel (`AlarmNotifier`)
3. Apple Reminders sync helpers

### Important Current Limitation

`task manager/` contains package-style relative imports (`from . import ...`) but the directory name has a space. As the code stands, the CLI is not directly executable as a normal Python package without refactoring/renaming the package directory.

## 2) Voice Interactive Chat Bot (`voice Interactive chat bot/`)

### Current Capability Snapshot

This prototype is a simple voice-to-LLM flow:

1. Listen from microphone (`SpeechRecognition`)
2. Transcribe using Wit.ai
3. Send text to Ollama model (`gemma3:4b`) for response
4. Print response to terminal

### Files and Roles

1. `main.py`: entry script (`listener -> transcriber -> lam_reasoning`)
2. `Prompt_input.py`: mic capture + Wit.ai transcription
3. `Reasoning.py`: Ollama chat + tool-decision helper
4. `API_and_tools.py`: helper tools (`get_location`, `get_weather`, `get_time`, `get_date`, `shut_down`)

### External Integrations

1. Wit.ai speech recognition API
2. Ollama local inference runtime
3. `ipapi.co` for location
4. `open-meteo.com` for weather

### Notes on Current State

1. `WIT_AI_KEY` is hardcoded in source.
2. `shut_down` is defined twice; second definition overrides first.
3. `decide_tools()` exists but is not wired into `main.py` flow.
4. This is a prototype script flow, not yet structured as a package.

### Typical Local Run (Prototype)

```bash
cd "voice Interactive chat bot"
python3 main.py
```

Prerequisites are currently manual (`SpeechRecognition`, `PyAudio`, `requests`, `ollama` Python client, local Ollama runtime, microphone permissions).

## 3) Virtual Space Constructor (`Virtual_space_constructor/`)

### What It Does

Manual capture 3D reconstruction pipeline:

1. Capture RGB frames from webcam
2. Predict monocular depth via MiDaS (`DPT_Large`)
3. Convert depth + color to 3D point cloud
4. Denoise point cloud (statistical outlier removal)
5. Align new captures to existing scene via ICP
6. Downsample with voxel grid
7. Save final merged point cloud to `scanned_scene.ply`

### Controls

In manual capture mode:

1. `SPACE`: capture current frame and merge into scene
2. `ESC`: finish and save

### Dependencies

From code and local notes:

1. `opencv-python` (`cv2`)
2. `torch`
3. `numpy`
4. `open3d`
5. Python 3.11 recommended for Open3D compatibility in this setup

### Typical Run

```bash
cd Virtual_space_constructor
python3 Main.py
```

### Notes on Current State

1. First run may download MiDaS artifacts via `torch.hub`.
2. Real-time performance is hardware-dependent and can be heavy.
3. Existing notes recommend lower-frequency/manual captures due to compute limits.

## Placeholder and Supporting Files

1. `clipThat.py`: currently empty placeholder.
2. `baymax architecture planning.md`: architecture notes and planning document.
3. `Baymax.jpeg`: project image asset.

## External Services and Runtime Matrix

Current modules rely on:

1. Notion API
2. AppleScript (`osascript`) for macOS automation
3. Wit.ai
4. Ollama local models
5. IP geolocation API (`ipapi.co`)
6. Weather API (`open-meteo`)
7. MiDaS model loading via `torch.hub`

## Known Gaps and Risks

1. No unified package/dependency management file at repo root (`requirements.txt` or `pyproject.toml` missing).
2. No automated test suite yet.
3. Mixed maturity levels across subprojects.
4. Some prototype code contains hardcoded secrets/config values.
5. Some paths/module naming conventions currently block direct packaging/execution workflows.

## Near-Term Consolidation Recommendations

1. Normalize package names/paths (remove spaces in Python package directories).
2. Add a single top-level dependency manifest.
3. Move secrets to environment variables or `.env` loading.
4. Add smoke tests for each prototype entry point.
5. Introduce one root launcher script with subcommands per module.

## Vision

BAYMAX is evolving toward a single personal-assistant platform. The current repository already contains concrete foundations in:

1. Task automation with Notion and reminder synchronization
2. Voice interaction and tool invocation experiments
3. Visual/3D spatial understanding experiments

The immediate opportunity is consolidation of these prototypes into one coherent runtime and developer workflow.
