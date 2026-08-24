# DEFERRED — Known limitations of the stepping-stone artifact

**Framing (2026-08-24)**: BAYMAX ships as a stepping-stone learning artifact per [PROJECT.md](PROJECT.md). This file documents what's INTENTIONALLY NOT in scope, so anyone reviewing the repo understands the artifact honestly.

Not "future work we're planning" — **not-implemented-and-not-planned** for this project. Previously framed as "deferred to v2/v3"; that framing implied continued development. That's not happening — the project ships at stepping-stone scope and Marv moves on.

If any of these ever get built, it would be a NEW project reusing BAYMAX's architecture as a foundation, not a continuation.

---

## Not in the shipped artifact

### Real API integrations
- **Real Google Calendar / Notion / Gmail / system clipboard adapters** — fake in-memory adapters only. No OAuth, no real API auth, no rate limits, no network flakiness handling.
- **Consequence**: BAYMAX cannot be used as a daily-driver assistant. Any successful eval scenario has zero real-world effect.

### Larger model
- **Only Qwen 2.5 1.5B + LoRA and OpenAI (gpt-4o-mini) supported.** Larger local models (Qwen 7B, Llama 3.1 8B, etc.) not integrated. Anthropic backend class placeholder mentioned in ADR 0011 but not implemented.
- **Consequence**: fine-tune quality ceiling is small-model tier. Cannot demonstrate what a 7B fine-tune would achieve without additional work.

### State persistence
- **In-memory state only per request.** SQLite state store designed in ADR 0007 but never implemented. Redis considered for future scale, never implemented.
- **Consequence**: no idempotency across requests, no cross-run history query, no audit/replay of past runs.

### Multi-turn dialog
- **Single-turn only.** No conversational memory across user turns within a session.
- **Consequence**: cannot handle "book another meeting like the one yesterday" or clarification follow-ups that create sub-tasks.

### Streaming inference
- **All-at-once responses.** No token-by-token streaming to caller.
- **Consequence**: latency feels awkward for interactive use; fine for batch eval.

### LLM-as-judge scoring
- **Deterministic scoring only.** ADR 0008 designed the judge protocol; implementation deferred and now not planned.
- **Consequence**: cannot score ambiguous scenarios where multiple tool-call sequences would be valid.

### Sub-task chains / multi-phase task modeling
- **Single-task-per-request.** No parent-child task hierarchy, no draft-then-verify-then-send workflow for irreversible actions.
- **Consequence**: agent cannot handle irreversible-tool patterns (like real Gmail send with verification gate).

### Cancellation / barge-in mid-tool-call
- **No mid-flight cancellation.**
- **Consequence**: user request that changes mind mid-execution has no clean abort path.

### Wall-clock / per-tool timeouts
- **Only `max_plan_steps` (step-count budget).** No real time budgets on tool calls.
- **Consequence**: fake adapters return in microseconds so no meaningful timeout risk; would matter for real adapters.

### OpenTelemetry / distributed tracing
- **Custom ndjson traces only.** OTel migration considered in ADR 0006, not implemented.
- **Consequence**: no cross-service trace correlation; single-process traces only. Fine at BAYMAX's scale.

### Deployment / production infrastructure
- **`uvicorn` manual start.** No launchd, no menu bar app, no Docker image, no cloud deployment, no health-check integration with any orchestrator.
- **Consequence**: not usable as a persistent background service without additional wrapping.

### Hallucinated entity / success detection
- **Basic scorer only.** Not detecting when agent invents email addresses / contacts / calendar events not in `initial_state`. Not detecting when agent claims success without supporting tool execution.
- **Consequence**: scoring is trustworthy for what it measures; blind to hallucination categories.

### Per-tool cost accounting for real APIs
- **Aggregate cost tracking only.** No per-tool spend attribution against real API quotas.
- **Consequence**: doesn't apply since no real APIs; would matter if real adapters ever ship.

### Sensitivity-based verification (beyond just reversibility)
- **Basic reversible/irreversible flag only** (designed in ADR 0009, not implemented since fakes are always reversible).
- **Consequence**: no per-scenario or per-arg sensitivity gating.

---

## Publication-review discipline items — dropped

Removed 2026-08-24 as publication-review overhead that no longer fits the stepping-stone scope:

- Bootstrapped 95% CI reporting requirement on aggregate metrics
- Pre-registered failure criterion per experiment
- 4-tier eval structure (compositional held-out, adversarial subset)
- Retry sensitivity sweep infrastructure (configurable N via env var, eval at multiple N values)
- Ablation sweep across LoRA rank / data mix / instruction template — reduced to "one basic variant, optional" per revised ROADMAP
- Formal experiment pre-registration files under `docs/experiments/`

Basic statistical honesty (sample size disclosed with every headline number) is retained.

---

## Architecture that WOULD support building any of the above

If Marv or someone else ever wanted to un-defer any of the above, BAYMAX's architecture is designed to allow it cleanly:

- Real adapter integration → matches the existing tool-adapter interface (ADR 0009 reversibility contract)
- Larger model → new backend class in the factory dict (ADR 0011)
- SQLite state store → schema defined in ADR 0007
- Multi-turn → hierarchical task_id already in v1 (ADR 0002)
- Streaming → additive method on backend (ADR 0011 §A5)
- LLM-as-judge → ADR 0008 defines the protocol

That extensibility is part of the artifact's engineering value. It's not going to be exercised by this project.

---

## Career / non-project deferrals (tracked elsewhere)

- **TADASHI-1 flagship** — see `future_work/tadashi_1_flagship.md` (gitignored)
- **Marbles-1 replication** — see `future_work/marbles_1_frequency_diffusion_vla.md` (gitignored)
- **open3d reconstruction** — see `future_work/open3d_world_recon_and_action_sim.md` (gitignored)
- **Master's application prep** — see `future_work/masters_program_targets.md` (gitignored)
