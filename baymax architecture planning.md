# BAYMAX Architecture Planning

Last updated: March 3, 2026  
Owner: BAYMAX workspace

---

## 1. Document Purpose

This document is the primary architecture and planning reference for the entire `BAYMAX/` folder.

It is not a summary note. It is an expanded technical and product blueprint that covers:

1. Current state of every active subproject.
2. Current limitations and future limitations to expect.
3. A practical plan to evolve BAYMAX into a multi-agent personal assistance product.
4. A feature backlog with concise value and utility notes.

---

## 2. Whole-Workspace Snapshot

Current active subprojects:

1. `task manager/`  
   Notion-backed task lifecycle, reminder polling, notifier channels, and DB-change watcher.
2. `voice Interactive chat bot/`  
   Voice input + transcription + local LLM response prototype.
3. `Virtual_space_constructor/`  
   Monocular-depth-to-point-cloud reconstruction prototype using MiDaS + Open3D.

Supporting root files:

1. `README.md` for high-level status.
2. `clipThat.py` placeholder for future clipping/capture workflow.
3. `Baymax.jpeg` branding/asset.

Current reality:

1. BAYMAX is a multi-prototype R&D workspace.
2. Product-level integration between subprojects is limited.
3. The design direction is promising, but operational hardening is required before autonomous multi-agent behavior.

---

## 3. Expanded Notes on Current State by Subproject

## 3.1 `task manager/` (Notion Task + Reminders)

### 3.1.1 Current Architecture

Module responsibilities:

1. `notion_client.py`  
   Thin Notion REST wrapper (`query_database`, `retrieve_page`, `update_page`, `create_page`, `create_database`).
2. `tasks.py`  
   Domain model (`Task`) and task CRUD helpers.
3. `reminders.py`  
   Polling reminder service with due-time checks, dedupe, and completion sync hooks.
4. `notifier.py`  
   Delivery channels and AppleScript bridges:
   - console output,
   - Messages app send,
   - macOS notification + beep,
   - Apple Reminders synchronization helpers.
5. `watcher.py`  
   Database fingerprint watcher and one-shot changepoint detection (cron-friendly mode).
6. `config.py`  
   Persistent local settings via `~/.baymax/config.json`.
7. `setup.py`  
   Notion Tasks database bootstrap schema.
8. `cli.py`  
   Operational command surface for all of the above.

### 3.1.2 Functional Strengths

1. Clear separation of transport (`notion_client`) and domain (`tasks`).
2. Practical reminder loop that handles immediate and periodic checks.
3. Support for both long-running watcher mode and cron one-shot mode.
4. Useful local persistence for channel/recipient preferences.
5. Existing hooks for future extension into additional channels and schedulers.

### 3.1.3 Current Limitations

1. Packaging/import limitation:
   - Folder name includes a space (`task manager/`) while code uses relative imports.
   - This blocks straightforward `python -m <package>` execution without refactor.
2. Platform coupling:
   - Notification and reminder sync are macOS/AppleScript dependent.
3. No test suite:
   - No automated validation for parser correctness, reminder dedupe, watcher signatures, or error handling.
4. Error resilience is basic:
   - Limited retry/backoff strategy for transient Notion/network failures.
5. State model is partial:
   - No canonical central state store for reminders, acknowledgments, and retry logs.
6. Observability is minimal:
   - Mostly print-based diagnostics.

### 3.1.4 Future Limitations to Plan For

1. Notion API constraints:
   - Rate limits and latency will become bottlenecks with higher polling frequencies and more agents.
2. Consistency drift:
   - Bidirectional sync between Notion and Apple Reminders can produce race conditions in edge cases.
3. Multi-agent contention:
   - Multiple agents updating same task fields can cause overwrite conflicts without versioning/merge strategy.
4. Cross-platform adoption:
   - AppleScript channels will not scale to Linux/Windows environments.

### 3.1.5 Planning Direction

1. Refactor into a proper package path (no spaces).
2. Introduce durable state/event log (SQLite or Postgres).
3. Add idempotency keys and optimistic concurrency/version checks for task updates.
4. Move from pure polling toward hybrid event-driven sync where possible.

---

## 3.2 `voice Interactive chat bot/` (Voice + LLM Prototype)

### 3.2.1 Current Architecture

1. `Prompt_input.py`:
   - microphone capture,
   - speech recognition via Wit.ai,
   - simple retry prompts.
2. `Reasoning.py`:
   - local LLM response via Ollama,
   - separate function for tool-decision JSON.
3. `API_and_tools.py`:
   - utility calls (`get_location`, `get_weather`, `get_time`, `get_date`, `shut_down`).
4. `main.py`:
   - linear entry flow: listen -> transcribe -> reason.

### 3.2.2 Functional Strengths

1. End-to-end voice interaction path exists and is runnable.
2. Local model inference path via Ollama avoids full cloud lock-in.
3. Tool abstraction has started and can be expanded into orchestrated function calling.

### 3.2.3 Current Limitations

1. Hardcoded secrets:
   - Wit.ai key is in source.
2. Tool execution safety:
   - `shut_down` utility exists and could be misused without permission guardrails.
3. Flow integration gap:
   - Tool-decision logic is not wired into runtime control flow.
4. Error/typing robustness is weak:
   - Potential undefined variable path in transcription failures.
5. Architecture is script-centric:
   - Not yet packaged as composable services or agent modules.
6. Context management is shallow:
   - No structured memory, no persistent conversation state, no persona policy engine.

### 3.2.4 Future Limitations to Plan For

1. Speech reliability and latency:
   - Real-time expectations require robust VAD, streaming ASR, and fallback models.
2. Safety and compliance:
   - Voice assistant actions need explicit consent and policy constraints.
3. Tool hallucination risk:
   - Model output for tool selection must be schema-validated and policy-checked.
4. Multi-device usage:
   - Current local script architecture does not yet support distributed clients.

### 3.2.5 Planning Direction

1. Move secrets to environment/config loading.
2. Implement a strict tool-invocation policy layer.
3. Add structured intent parser with fallback rules.
4. Introduce session memory and command audit trail.

---

## 3.3 `Virtual_space_constructor/` (3D Reconstruction Prototype)

### 3.3.1 Current Architecture

1. Camera capture with OpenCV.
2. Depth estimation with MiDaS (`DPT_Large`) through `torch.hub`.
3. Depth + RGB conversion to colored 3D point cloud.
4. Noise reduction with statistical outlier removal.
5. Cloud alignment using ICP registration.
6. Voxel downsampling and `.ply` export.

### 3.3.2 Functional Strengths

1. Real working pipeline from live camera frames to merged 3D output.
2. Demonstrates capability for spatial perception and environmental modeling.
3. Includes practical denoise and registration primitives, not just raw depth output.

### 3.3.3 Current Limitations

1. Compute intensity:
   - MiDaS `DPT_Large` is expensive for commodity real-time use.
2. Calibration quality:
   - Focal assumptions are fixed and not camera-calibrated.
3. Drift/noise accumulation:
   - Long capture sessions may compound alignment errors.
4. Runtime fragility:
   - No adaptive quality mode based on hardware load.
5. Standalone status:
   - No integration yet with voice/task stack or shared planner.

### 3.3.4 Future Limitations to Plan For

1. Product fit clarity:
   - 3D perception must tie to concrete assistant use cases, not just technical novelty.
2. Data volume:
   - Point cloud storage and versioning can become expensive quickly.
3. Real-time expectations:
   - Live reconstruction at useful fidelity may require model/hardware changes.
4. Privacy concerns:
   - Continuous scene capture introduces strong local privacy requirements.

### 3.3.5 Planning Direction

1. Define narrow use cases first (room map updates, object localization hints, safety checks).
2. Add calibration pipeline and capture quality controls.
3. Store compact scene descriptors for agent consumption, not only full point clouds.
4. Expose a read-only scene query API for downstream agents.

---

## 3.4 Cross-Project System Limitations (Current and Future)

Current cross-project constraints:

1. No unified package/dependency management at root.
2. No single orchestrator process for all capabilities.
3. No shared event bus or normalized internal schema across modules.
4. No central policy engine controlling tool permissions.
5. No integrated observability (metrics, traces, structured logs).

Future cross-project risks:

1. Agent conflicts and write collisions without coordination protocol.
2. Increased operational complexity when mixing cloud APIs, local models, and OS-level automations.
3. User trust risk without explainability and action audit logs.
4. Scalability limitations if all workflows remain polling-based.

---

## 4. Target Product: BAYMAX as a Multi-Agent Personal Assistant

## 4.1 Product Goal

Evolve BAYMAX into a user-trusted assistant that can:

1. Understand voice/text context.
2. Maintain persistent personal state (tasks, routines, reminders, preferences).
3. Coordinate specialized agents to execute safe actions.
4. Explain decisions and request confirmation for sensitive operations.

## 4.2 Target Multi-Agent Architecture

Core layers:

1. Interface Layer:
   - Voice interface,
   - CLI,
   - future chat/web/mobile clients.
2. Orchestration Layer:
   - intent classifier,
   - planner,
   - agent router,
   - scheduler,
   - permission gate.
3. Agent Layer (specialists):
   - TaskAgent,
   - ReminderAgent,
   - CalendarAgent,
   - FinanceAgent,
   - Capture/ClipAgent,
   - KnowledgeAgent,
   - VisionAgent.
4. Tool Layer:
   - Notion adapter,
   - OS notification adapter,
   - message adapter,
   - weather/location adapters,
   - local model adapters.
5. Memory + Data Layer:
   - profile/preferences,
   - working memory,
   - event log,
   - task/transaction stores,
   - optional vector memory.
6. Safety + Governance Layer:
   - action policies,
   - sensitive-action confirmation,
   - audit logs,
   - secrets management.

## 4.3 Agent Coordination Model

1. Planner receives intent and outputs a task graph.
2. Router selects agents and tools based on capabilities + policy.
3. Agents execute with explicit contracts and structured outputs.
4. State updates flow through a canonical event model.
5. User receives result + explanation + follow-up options.

---

## 5. Roadmap to Productization

## 5.1 Phase 0: Foundation Hardening (Immediate)

1. Normalize directory/package names and import structure.
2. Add root dependency strategy (`pyproject.toml` or `requirements` split).
3. Introduce environment-based secret handling everywhere.
4. Add baseline tests for parser, reminders, and tool-selection logic.
5. Add structured logging and error telemetry.

## 5.2 Phase 1: Unified Assistant Core

1. Build a single `baymax_core` runtime process.
2. Define common data contracts for intents, tasks, events, and tool results.
3. Integrate `task manager` as first productionized agent/tool set.
4. Add policy-gated tool execution with confirmation prompts.

## 5.3 Phase 2: Multi-Agent Expansion

1. Productionize voice pipeline with safer tool invocation.
2. Add CalendarAgent and NotificationAgent with cross-platform channels.
3. Add Knowledge/Memory agent for contextual continuity.
4. Add scheduler that supports both reactive and proactive tasks.

## 5.4 Phase 3: Advanced Modalities and Autonomy

1. Integrate VisionAgent using scene descriptors from `Virtual_space_constructor`.
2. Add multi-step plans with checkpointing/recovery.
3. Add user-visible “Why I did this” explanations and full action timeline.
4. Add adaptive personalization loops from feedback.

---

## 6. Future Feature Backlog (Concise Value List)

1. Unified command center UI  
   Why: single control surface for all agent actions.  
   Utility: reduces friction and improves transparency.

2. Cross-platform notification gateway (email/SMS/Telegram/Discord/push)  
   Why: current channels are macOS-centric.  
   Utility: reliable reminders across device ecosystems.

3. Calendar bi-directional sync  
   Why: tasks/reminders need schedule awareness.  
   Utility: fewer missed tasks and smarter time-aware planning.

4. Recurring task/routine engine  
   Why: recurring habits are core to personal assistance.  
   Utility: automatic regeneration and tracking of routine work.

5. Natural-language planning with approval checkpoints  
   Why: users want “do this for me” flows with control.  
   Utility: faster execution while preserving trust/safety.

6. Personal knowledge memory with retrieval  
   Why: continuity over days/weeks is required for “assistant” behavior.  
   Utility: contextual responses and reduced repetitive setup.

7. Finance tracker agent  
   Why: budgeting and spend-awareness are frequent assistant tasks.  
   Utility: proactive alerts, summaries, and decision support.

8. Clip/Capture agent (`clipThat`)  
   Why: users collect links/snippets/ideas continuously.  
   Utility: structured capture with searchable recall and tagging.

9. Voice wake-word + streaming ASR  
   Why: current voice loop is manual and stop-start.  
   Utility: lower interaction friction and better real-time feel.

10. Tool sandbox and permission profiles  
    Why: some tools (shutdown/system actions) are high-risk.  
    Utility: safer operation and user-configurable trust boundaries.

11. Explainability panel  
    Why: autonomous actions require accountability.  
    Utility: higher trust through clear rationale and execution logs.

12. Vision-based context hints  
    Why: scene understanding can improve reminders and assistance relevance.  
    Utility: location/object-aware prompts and workflows.

13. Offline-first core mode  
    Why: reliability should not depend entirely on network/cloud APIs.  
    Utility: resilient baseline assistant behavior.

14. Plugin/adapter SDK for external tools  
    Why: long-term growth needs extensibility beyond built-ins.  
    Utility: faster ecosystem expansion without core rewrites.

---

## 7. Definition of Success for BAYMAX v1

BAYMAX v1 should satisfy:

1. One unified runtime controlling multiple specialized agents.
2. Safe and auditable tool execution with confirmation for sensitive actions.
3. Reliable task/reminder lifecycle with cross-platform delivery.
4. Persistent user context and memory with explicit controls.
5. Production-level observability, tests, and failure recovery.

---

## 8. Planning Notes for Ongoing Updates

When updating this document in future:

1. Keep current-state sections evidence-based from actual code paths.
2. Track limitations as “resolved / in progress / new”.
3. Update roadmap with completed milestones and date stamps.
4. Keep backlog concise and outcome-oriented.

