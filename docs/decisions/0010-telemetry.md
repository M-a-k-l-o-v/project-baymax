# ADR 0010 — Telemetry

**Status**: Proposed (Marv to confirm)
**Date**: 2026-06-20
**Author**: Marv
**Related**: [ADR 0002](0002-tool-call-schema.md), [ADR 0006](0006-trace-format.md), [ADR 0007](0007-state-store.md), [src/baymax/telemetry/logger.py](../../src/baymax/telemetry/logger.py)

---

## Context

BAYMAX needs telemetry that:

1. Records every event in the agent loop with enough context to reconstruct what happened after the fact
2. Never leaks secrets (API keys, auth tokens, OAuth credentials) into trace files, log files, or stderr
3. Correlates events within a single request across modules (agent core → inference backend → tool adapter)
4. Is consumed both by Ronin's eval harness (for failure analysis) and by developer eyeballs (for debugging during dev)
5. Has zero new infrastructure requirements in v1 — same posture as state store ([ADR 0007](0007-state-store.md)) and trace format ([ADR 0006](0006-trace-format.md))

The constraint set is shaped by:

- [ADR 0002 §6](0002-tool-call-schema.md): environment-based auth → tokens must never appear in traces
- [ADR 0006](0006-trace-format.md): ndjson trace format — telemetry emits ndjson events
- Single-process v1 — no distributed tracing requirement yet

The choice surface is "which library writes the JSON" — not whether to use JSON. The candidates:

- `structlog` — structured logging library; emits dict events; pluggable processors
- Python stdlib `logging` with a custom JSON formatter — works but ergonomically rough
- OpenTelemetry SDK directly — full distributed-tracing semantics, overkill for v1
- Roll our own — re-invents the wheel for no benefit

---

## Decision

**`structlog` for v1**, configured to:

- Emit ndjson events (one event per line, matching [ADR 0006](0006-trace-format.md))
- Run a redaction processor on every event before serialisation
- Inject a `trace_id` context variable so events across modules within one request correlate
- Write to `traces/<run_id>/<task_id>.jsonl` (per ADR 0006 path)

### Redaction processor

Any event field whose key matches one of the following case-insensitive patterns is replaced with `[REDACTED]` before the event is written:

- `auth*`
- `token*`
- `key*`
- `password*`
- `secret*`
- `authorization*`
- `bearer*`

The processor runs as the LAST step in structlog's chain, after all event construction. This means any code path that accidentally includes a credential in an event payload gets caught at the chokepoint, not at the call site.

### Trace correlation

`trace_id` is bound via `structlog.contextvars.bind_contextvars(trace_id=...)` at the start of each request. All subsequent events emitted in that request (across modules) automatically include the trace_id. The state store ([ADR 0007](0007-state-store.md)) joins traces to tasks via this id.

### Event shape

Matches [ADR 0006](0006-trace-format.md) event shape exactly — telemetry is the writer; ADR 0006 is the schema.

### OpenTelemetry deferral

OTel format remains deferred to v2 pending Ronin discussion (per [RONIN_SYNC.txt](../../RONIN_SYNC.txt) Tier 1 #1 and [ADR 0006](0006-trace-format.md)). When OTel migration happens, structlog's processor chain swaps the final JSON formatter for an OTel exporter — the rest of the emission code is unaffected.

---

## Reasoning

[TODO Marv: write 3-5 sentences in your voice explaining WHY structlog over stdlib logging or rolling our own, WHY redaction at the LAST step in the processor chain (not at the call site), WHY contextvars over passing trace_id through call signatures. Likely themes: structlog's processor chain gives you a single chokepoint for redaction that can't be bypassed by a forgotten log statement; redaction at emission removes the risk of "what if someone adds a new credential field next week?"; contextvars solve the correlation problem without polluting every function signature with trace_id; this is the kind of cross-cutting concern that should live in infrastructure, not application logic. This section gets quoted under interview drilling.]

---

## Alternatives considered

### Alternative A — Python stdlib `logging` with a custom JSON formatter

Use `logging.getLogger(__name__)`, configure a custom formatter that emits JSON, add a filter for redaction.

why rejected — stdlib logging's data model is "message + optional extra dict"; you can't naturally pass structured event payloads. Custom formatters get ugly fast. Filters run BEFORE message construction in some paths, making redaction unreliable. Structlog was built specifically for this use case.

### Alternative B — OpenTelemetry SDK directly

Adopt OTel's tracer / span / attribute model; use the OTel SDK's exporters and instrumentation libraries.

why rejected — OTel buys distributed-trace correlation we don't need yet (single-process v1). The SDK is heavy (30+ MB dependencies). The semantic conventions assume a span-based mental model that doesn't perfectly match our event-stream model. ADR 0006 already deferred OTel to v2; this ADR follows that decision.

### Alternative C — Roll our own logger

Write a small custom logger class that emits ndjson, handles redaction, manages context.

why rejected — re-implements structlog, badly. Structlog is mature, well-tested, has the right shape. The only reason to roll our own would be if structlog had some specific limitation we hit — it doesn't.

### Alternative D — `loguru`

A popular alternative to structlog with a simpler API.

why rejected — loguru's redaction story is weaker (you have to filter messages by regex, no native field-level processor chain). For "must redact every credential field every time" requirements, structlog's processor chain is the right primitive.

---

## Consequences

### Positive

- Redaction is a single chokepoint that can't be bypassed by a forgotten log statement
- Adding fields to events is trivial (just pass them as kwargs to the logger call)
- Trace correlation across modules is implicit (no manual trace_id threading through call signatures)
- Migration to OTel in v2 is local to the structlog processor chain — emission sites are unaffected
- Cost per event is sub-microsecond on modern Macs (benchmark Phase 1 confirms)

### Negative

- structlog adds a dependency and a small learning curve for new contributors
- The processor chain is the kind of "implicit configuration" that surprises people the first time they hit it — needs to be documented in `src/baymax/telemetry/README.md`
- Contextvars don't propagate across `asyncio.create_task` boundaries unless you propagate manually; need a wrapper

### Neutral

- Redaction patterns are listed in code; any new credential category not on the list could leak. Mitigation: review the redaction list quarterly as new adapters are added

---

## Open questions / follow-ups

- **Asyncio context propagation**: confirm that contextvars survive `asyncio.gather` boundaries in our specific call paths; test with a tool dispatched via `gather` in Phase 1.
- **Per-module log levels**: not needed yet (everything emits at INFO). Add per-module filtering when log volume becomes a problem.
- **Sampling**: not in v1 (every event is emitted). Add per-event-category sampling rates when volume is a problem at Phase 3.
- **Sensitive payload redaction beyond credentials**: e.g., should the body of a user's email draft be redacted in traces? Not in v1 (the agent has to work with the content). Worth a v2 discussion when real adapters arrive and traces start including real personal data.
- **OTel migration trigger**: tracked alongside ADR 0006 in [DEFERRED.md](../DEFERRED.md).

---

## References

- structlog docs: https://www.structlog.org
- structlog processor chain pattern: https://www.structlog.org/en/stable/processors.html
- Python contextvars (PEP 567): https://peps.python.org/pep-0567/
- [ADR 0002 §6](0002-tool-call-schema.md) — env-based auth requirement that drives redaction
- [ADR 0006](0006-trace-format.md) — ndjson event format this ADR emits
- [ADR 0007](0007-state-store.md) — state store this ADR's trace_ids join into
- [RONIN_SYNC.txt](../../RONIN_SYNC.txt) Tier 1 #1 — OTel-vs-custom discussion
