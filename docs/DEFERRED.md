# Deferred Scope — Things Pushed to Future Phases

Source: design discussion 2026-06-17 between Marv and Claude during tool-call contract design.

This file captures features, patterns, and decisions intentionally pushed to later versions to keep v1 shippable. Each entry includes the trigger (when to revisit) and notes the rationale.

When a v2 / v3 milestone arrives, re-read this file and decide what to lift back into scope.

---

## Deferred to v2 (post-Phase 1 ship; tentative Phase 3-4 work)

### Sub-task chains (parent-child task IDs)
- **Pattern**: Clarification follow-ups create child tasks (e.g., 1.0 → 1.1). Retry creates child tasks. Child inherits parent context.
- **Why deferred**: Ronin's Phase 1 scenarios are single-turn; expected_behavior `clarification` is terminal. Multi-turn flows would break scorer assumptions.
- **Revisit when**: Multi-turn scenarios are designed (Phase 3 v2 expansion).

### Multi-phase tasks (verify-first for irreversible tools)
- **Pattern**: Tools that cannot be undone (real `gmail.send_email`) get wrapped in a draft-then-verify-then-send sequence. The verification step is a sub-task.
- **Why deferred**: Requires sub-task model (above) AND real adapters. v1 fakes are always reversible, so the pattern isn't load-bearing yet.
- **Revisit when**: Real `gmail.send_email` adapter ships, OR scenarios start including irreversible-tool tests.

### Multi-turn user sessions
- **Pattern**: User and agent exchange multiple turns; agent maintains conversational state across the session.
- **Why deferred**: Phase 1 eval is single-turn request → response.
- **Revisit when**: Phase 3 v2 expansion adds multi-turn scenarios.

### LLM-as-judge for ambiguous scenarios
- **Pattern**: Scenarios marked `difficulty: ambiguous` use an LLM to score semantic equivalence rather than strict matching.
- **Why deferred**: Ronin's v1 scorer is explicitly deterministic. SCORING.md lists "no LLM-as-judge" as a v1 non-goal.
- **Revisit when**: Ronin opens an ADR for the judge protocol (planned ADR 0008).

### Context inheritance across sub-tasks
- **Pattern**: When a sub-task (retry, clarification follow-up) is created, it inherits parent's context plus gets new context (timeout error, retry reason).
- **Why deferred**: Depends on sub-task chains (above).
- **Revisit when**: Sub-tasks are implemented.

### Real-API tool adapters (not just fakes)
- **Pattern**: Real Notion / Google Calendar / Gmail / system clipboard integrations replacing the in-memory fakes.
- **Why deferred**: v1 uses fakes deliberately for determinism and speed. Real adapters introduce rate limits, auth, and network flakiness.
- **Revisit when**: Eval baseline numbers are stable on fakes AND there's a use case for real-world testing.

### Hallucinated entity / state / success detection in scorer
- **Pattern**: Detect when agent invents email addresses, contacts, calendar events, Notion tasks that don't exist in `initial_state`. Detect when agent claims success without supporting tool execution.
- **Why deferred**: Ronin's SCORING.md flags these as "Planned Scoring Work" — not in v1.
- **Revisit when**: Ronin starts the planned scorer expansion. Marv's `task_done` vs `task_success` distinction is the architectural hook for this.

### Pre-validation telemetry consumed by Ronin's scorer
- **Pattern**: Marv's agent emits telemetry for failed-task_file-construction events. Currently logged but not scored.
- **Why deferred**: Cross-team coordination work. Marv's contract supports it; Ronin's scorer doesn't yet consume it.
- **Revisit when**: Scoring work expands per `hallucinated_*` flag above.

### Per-tool cost accounting (real-API quotas)
- **Pattern**: Some real APIs (Notion, Gmail) have per-call costs or quotas. RunCost should track per-tool spend, not just aggregate.
- **Why deferred**: Real adapters needed first.
- **Revisit when**: Real adapters ship.

### Cancellation / barge-in mid-tool-call
- **Pattern**: User can abort a tool call while it's in flight (not just between tool calls).
- **Why deferred**: Roadmap labels this "optional stretch" for Phase 3.
- **Revisit when**: Phase 3 multi-turn work or earlier if streaming inference design forces it.

### Wall-clock / per-tool timeouts
- **Pattern**: v1 has `max_plan_steps` (step-count budget only). v2 needs real time budgets — likely per-tool timeouts declared by the adapter, not a single global request-level timeout (different tools have different time profiles).
- **Why deferred**: v1 fakes return in microseconds — no meaningful time risk.
- **Revisit when**: Real adapters arrive (Phase 3+). Add `timeout_seconds: float` to the adapter contract, enforce via dispatcher with a deadline.

### Streaming response (response_text + optional tool_call events)
- **Pattern**: Stream the agent's response text as model generates tokens; optionally emit tool_call events as each tool executes.
- **Why deferred**: v1 client = Ronin's eval runner, which doesn't benefit from streaming. Adds complexity for no v1 value.
- **Revisit when**: Interactive client added (CLI / web UI / voice frontend). Phase 2-3 likely.

### Sensitivity-based verification gate (beyond just reversibility)
- **Pattern**: Verification flag triggered not only by `reversible: false` but also by per-scenario or per-arg-value sensitivity (e.g., calendar event with CEO; email to legal counsel).
- **Why deferred**: v1's reversibility-only rule covers the irreversible-tool case. Sensitivity gating is real-world UX polish.
- **Revisit when**: Real-API adapters in use and user-facing UX matters.

### `_contains` agent-emit support
- **Pattern**: Agent could emit partial-match values when uncertain (e.g., `body_contains: "...thanks"` when only partially confident of phrasing).
- **Why deferred**: v1 agent emits plain values; eval-side handles partial matching. Pending v2 conversation with Ronin.
- **Revisit when**: Discussing v2 contract evolution with Ronin.

### Multi-phase task modeling (versioned task_File vs sub-task chain)
- **Pattern**: Multi-phase tasks (e.g., gmail.create_draft → verify → send_with_draft_id) need either (a) versioned mutable task_File or (b) sub-task chain with context inheritance.
- **Why deferred**: v1 fakes are atomic; multi-phase pattern doesn't ship until real adapters and irreversible-tool support.
- **Revisit when**: Designing irreversible-tool real-adapter integration in v2.

---

## Deferred to v3 (post-v2; production-grade)

### Redis state store (multi-process / multi-machine support)
- **Pattern**: Move from SQLite (v1) to Redis when state needs to be shared across processes or machines.
- **Why deferred**: Single-machine SQLite handles v1-v2 needs. Redis adds Docker complexity unnecessarily early.
- **Revisit when**: First time you need two BAYMAX processes (e.g., separate web/API frontend, scheduler, or multi-user deployment).

### Distributed eval runs
- **Pattern**: Run eval scenarios in parallel across multiple worker processes / machines for throughput.
- **Why deferred**: 200 scenarios sequentially is tolerable. Distribution adds infrastructure cost.
- **Revisit when**: Scenario count crosses ~500 OR per-scenario cost crosses a threshold.

### Real-time multi-machine deployment
- **Pattern**: Production-grade serving with load balancing, health checks, autoscaling.
- **Why deferred**: BAYMAX is single-user personal-assistant scope. Multi-user is post-v3.
- **Revisit when**: Project pivots to multi-user OR open-source release with multiple deployments.

---

## Decisions still open (not yet deferred — Marv to lock)

### Trace format choice
- **Question**: OpenTelemetry vs custom JSON?
- **Blocks**: ADR 0006
- **Status**: discuss with Ronin (he may use traces for eval debugging)

## Decisions locked 2026-06-17/18

- **Verification flag**: always-on for irreversible tools (adapter declares `reversible: bool` + `requires_verification: bool`, the latter auto-set when reversible is false). Sensitivity-based refinement deferred to v2.
- **task_id format**: hierarchical `<task_int>.<phase_int>`, e.g. `1.0`, `1.1`. For Phase 1 single-turn, all IDs are `N.0`. Consider prefixing with `run_id` for cross-session uniqueness.
- **Auth model**: environment variables, adapters fetch credentials directly. Telemetry must redact auth_*/token/key/password fields (belongs in telemetry ADR).
- **`_contains` convention scope (v1)**: eval-side only — agent emits plain values, Ronin's scorer handles substring matching. v2 discussion pending.
- **Streaming response (v1)**: all-at-once. Eval runner doesn't benefit from streaming. Streaming deferred to v2 when interactive clients matter (added to v2 deferral list below).
- **Multi-phase task model**: v1 doesn't implement multi-phase. For v2, two viable paths (versioned task_File OR sub-task with context inheritance). Marv's preference: single conceptual task with cumulative context. Final modeling choice deferred to v2. v1 must NOT preclude either path (keep hierarchical task_id, don't bake "single mutable task" assumptions into task_File class).

---

## Career / non-project deferrals (already tracked elsewhere)

These are not BAYMAX-scope but listed so they're not forgotten:

- **TADASHI-2 motion priors flagship** — target window: Master's M2 (2028-2029). See [future_work/tadashi_2_motion_priors.md](../future_work/tadashi_2_motion_priors.md) (gitignored, local).
- **Master's program applications** — apply Jan-Mar 2027 for Sept 2027 start. See [future_work/masters_program_targets.md](../future_work/masters_program_targets.md) (gitignored, local).
- **ML foundations summer self-study** — Jul-Sep 2026, see [docs/personal/marv_ml_summer_prep.md](personal/marv_ml_summer_prep.md) (gitignored, local).
- **Outreach cadence** — 5 high-quality reaches per week. Target list to build Sept-Dec 2026.

---

## How to use this file

- **At v2 kickoff**: read top section, decide which v2-deferred items are in scope
- **At v3 kickoff**: same for v3 section
- **Whenever an "open decision" gets locked**: move it to its ADR and delete from the "open decisions" section here
- **Whenever a new deferral happens**: add to the appropriate section with rationale

This file is the project's source of truth for "things we know we'd do later." If something doesn't appear here AND isn't in active ADRs, it doesn't exist as a future commitment.
