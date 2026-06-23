# ADR 0007 — State store

**Status**: Confirmed (locked in [RONIN_SYNC.txt](../../RONIN_SYNC.txt) Tier 2 #8)
**Date**: 2026-06-20
**Author**: Marv
**Related**: [ADR 0001](0001-agent-loop-pattern.md), [ADR 0002](0002-tool-call-schema.md), [ADR 0006](0006-trace-format.md), [docs/DEFERRED.md](../DEFERRED.md)

---

## Context

The agent persists state across the lifetime of a request and across multiple eval runs:

- `task_file` objects for each request (see [ADR 0002](0002-tool-call-schema.md))
- Action logs (per-tool dispatch results, ordered)
- Cost accumulation per task
- Idempotency tracking (request hashes for duplicate detection per ADR 0002 §6)
- Reversibility state for rollback (per [ADR 0009](0009-abort-and-rollback.md))
- Cross-run history for eval analysis (so a benchmark run can be replayed later)

For v1:

- Single-process, single-machine eval runs
- ~100 scenarios per benchmark run, ~10 tool calls per scenario worst-case → low write volume
- No external services running yet
- Ronin's eval harness reads runs back from disk for analysis

For v3 (potential):

- Multi-process eval runs (sharded scenarios across machines) might need a shared state store
- Higher concurrency might benefit from a process-external store

---

## Decision

**SQLite for v1.** A single `baymax.sqlite` file under `data/runs/<run_id>/baymax.sqlite` per benchmark run. Single connection per process, WAL mode enabled for concurrent reads alongside writes (Ronin's eval harness can read live without blocking the agent).

**Redis at v3, conditional**. If and only if multi-process eval runs need shared state. Trigger: a concrete v3 requirement that SQLite cannot satisfy. Not pre-emptively migrated.

Schema (v1, evolving — managed via Alembic migrations):

```text
runs(run_id PK, started_at, finished_at, backend, model_version, scenario_set_version)
tasks(task_id PK, run_id FK, request_text, status, created_at, completed_at, cost_total, response_text)
task_files(task_id FK, version, body JSON)               # task_file evolves across recovery passes
action_log(task_id FK, step_idx, tool, arguments JSON, result JSON, started_at, finished_at, error_type)
idempotency(request_hash PK, task_id, expires_at)
```

Trace data does NOT live here — it goes to jsonl files per [ADR 0006](0006-trace-format.md). State store is for queryable structured state; traces are for forensic event streams. Separating them prevents one's lifecycle (rollback, expiry) from breaking the other.

---

## Reasoning

[TODO Marv: write 3-5 sentences in your voice explaining WHY SQLite for v1 (not Redis, not Postgres, not in-memory), WHY separating state store from trace store (ADR 0006), WHY WAL mode matters. Likely themes from RONIN_SYNC.txt #8 ("catch up to late roadmap, Redis when v3"): zero infra is the v1 priority because Ronin needs to read runs immediately for eval analysis; SQLite gives durability + transactions + concurrent reads with no daemon; separating state and traces means a rollback doesn't corrupt the trace stream; Redis is a v3 problem we'll solve when we have a concrete multi-process requirement. This section gets quoted under interview drilling.]

---

## Alternatives considered

### Alternative A — Postgres from v1

Run a Postgres container alongside the eval harness; agent + eval both connect to it.

why rejected — Postgres is a container to run, a config to manage, a connection pool to size, and a backup strategy to design. v1 has none of these problems. Postgres becomes correct when we have concurrent writers (multiple agent processes), but v1 doesn't.

### Alternative B — Redis from v1

Use Redis (in-memory + AOF persistence) as the v1 state store.

why rejected — Redis is fast and concurrent but loses on durability primitives (transactions across keys are awkward; ACID-grade integrity requires care). And there's nothing v1 needs that SQLite doesn't already give us. Adopting Redis early means paying its operational cost (separate process, RDB/AOF tuning) for capability we don't use. Per RONIN_SYNC.txt #8: deferred to v3 conditional on multi-process need.

### Alternative C — File-based JSON / pickle blobs

Write task_files and action logs as JSON files under `data/runs/<run_id>/tasks/<task_id>.json`.

why rejected — no transactions (a crash mid-write leaves a broken JSON file), no cross-task queries (Ronin's eval needs to ask "all tasks where the agent used calendar.create_event" — that's a `SELECT` not a directory scan), and no idempotency primitives. SQLite gives all three for less work than rolling our own.

### Alternative D — In-memory only

Keep all state in process memory; lose everything on process exit.

why rejected — eval analysis happens AFTER the run ends. In-memory state means no analysis. Also rules out crash recovery and run resumption.

---

## Consequences

### Positive

- Zero new infrastructure in v1 (matches [ADR 0006](0006-trace-format.md)'s same posture for traces)
- Transactions: action log writes are atomic with status updates; no inconsistent state on crash
- Queryable: Ronin's eval can `SELECT * FROM action_log WHERE error_type = 'intent_error'` directly
- WAL mode means readers and the writer don't block each other; eval harness can watch a live run
- Backups are `cp baymax.sqlite baymax.sqlite.bak` — trivial

### Negative

- Single writer per file — would not scale to multi-process eval (deferred per the Redis trigger)
- Schema migrations are real (Alembic adds a dependency + workflow) — but the alternative is uncontrolled schema drift, which is worse
- SQLite locks the whole file briefly during writes; high concurrency triggers `database is locked` errors. v1 single-writer avoids this.

### Neutral

- Storage on disk grows linearly with runs; needs a retention policy by Phase 3 (matches the jsonl traces situation)

---

## Open questions / follow-ups

- **Schema versioning**: managed via Alembic. v1 schema is "Version 1"; any change to the tables above bumps the migration version.
- **Run retention**: not enforced yet. Add a `scripts/retention.py` in Phase 3 to drop old runs.
- **Read amplification**: Ronin's eval queries should be benchmarked against a 200-scenario run by end of Phase 1 to confirm SQLite query time is acceptable.
- **Concurrent eval runs on the same machine**: each run gets its own `baymax.sqlite` file under its own `data/runs/<run_id>/` directory — no cross-run lock contention.
- **Redis migration trigger documented in [DEFERRED.md](../DEFERRED.md)**: multi-process eval runs sharing state.

---

## References

- SQLite WAL mode: https://www.sqlite.org/wal.html
- Alembic: https://alembic.sqlalchemy.org/
- [RONIN_SYNC.txt](../../RONIN_SYNC.txt) Tier 2 #8 — decision locked
- [DEFERRED.md](../DEFERRED.md) — Redis migration trigger
