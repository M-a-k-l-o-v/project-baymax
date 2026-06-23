"""Structured logging + cost tracking.

Per ADR 0010 (telemetry — proposed). Decision: structlog for v1, custom JSON
events. OpenTelemetry trace format deferred pending Ronin discussion (ADR 0006).

The logger emits JSON-line events with a trace_id correlating all events for
one request. Cost is tracked separately per `cost_usd` increments.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

# DECISION: redact any field matching these substring patterns from logged events.
# Per ADR 0002 §6 — environment-based auth requires that tokens never appear in traces.
_REDACT_PATTERNS = ("token", "api_key", "apikey", "password", "secret", "authorization")


def _redact(obj: Any) -> Any:
    """Recursively redact sensitive fields from a structured event."""
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if any(p in k.lower() for p in _REDACT_PATTERNS) else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CostAccumulator:
    """Per-trace cost rollup."""

    input_tokens: int = 0
    output_tokens: int = 0
    tool_call_count: int = 0
    usd: float = 0.0

    def add_llm(self, *, input_tokens: int, output_tokens: int, usd: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.usd += usd

    def add_tool_call(self) -> None:
        self.tool_call_count += 1


@dataclass
class TelemetryTrace:
    """One trace = one full request lifecycle."""

    trace_id: str
    task_id: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    cost: CostAccumulator = field(default_factory=CostAccumulator)
    events: list[dict[str, Any]] = field(default_factory=list)


class TelemetryLogger:
    """Structured logger for one BAYMAX process.

    Usage:
        logger = TelemetryLogger.configure(output_path="traces.jsonl")
        with logger.trace("user_request_handler") as trace:
            trace.task_id = "run_1.0.0"
            logger.event(trace, "intent_interpreted", intent="create_event")
            trace.cost.add_llm(input_tokens=120, output_tokens=40, usd=0.0001)
    """

    def __init__(self, output_stream: Any = sys.stderr) -> None:
        self._output = output_stream
        self._logger = logging.getLogger("baymax.telemetry")

    @classmethod
    def configure(cls, output_path: str | None = None) -> "TelemetryLogger":
        """Construct a TelemetryLogger.

        If output_path is provided, events are written line-delimited JSON to that file.
        Otherwise events go to stderr.
        """
        if output_path is None:
            return cls(output_stream=sys.stderr)
        # DECISION: open in append mode so multiple runs accumulate. v2 may rotate.
        stream = open(output_path, "a", encoding="utf-8")  # noqa: SIM115 — long-lived
        return cls(output_stream=stream)

    @contextmanager
    def trace(self, root_event: str, **extra: Any) -> Iterator[TelemetryTrace]:
        """Open a trace context. All events emitted inside share the same trace_id."""
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        t = TelemetryTrace(trace_id=trace_id)
        self.event(t, root_event, status="started", **extra)
        try:
            yield t
        except Exception as exc:  # pragma: no cover — exception path
            self.event(t, root_event, status="errored", error=repr(exc))
            t.completed_at = datetime.now(timezone.utc)
            self._emit_trace_summary(t)
            raise
        else:
            t.completed_at = datetime.now(timezone.utc)
            self.event(t, root_event, status="completed")
            self._emit_trace_summary(t)

    def event(self, trace: TelemetryTrace, event_name: str, **fields: Any) -> None:
        """Emit one event within a trace."""
        record = {
            "ts": _now_iso(),
            "trace_id": trace.trace_id,
            "task_id": trace.task_id,
            "event": event_name,
            **_redact(fields),
        }
        trace.events.append(record)
        self._write(record)

    def _emit_trace_summary(self, trace: TelemetryTrace) -> None:
        """Emit final summary event with rollup metrics."""
        summary = {
            "ts": _now_iso(),
            "trace_id": trace.trace_id,
            "task_id": trace.task_id,
            "event": "trace_summary",
            "started_at": trace.started_at.isoformat(),
            "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
            "duration_ms": (
                int((trace.completed_at - trace.started_at).total_seconds() * 1000)
                if trace.completed_at
                else None
            ),
            "input_tokens": trace.cost.input_tokens,
            "output_tokens": trace.cost.output_tokens,
            "tool_call_count": trace.cost.tool_call_count,
            "cost_usd": round(trace.cost.usd, 6),
            "event_count": len(trace.events),
        }
        self._write(summary)

    def _write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, default=str)
        try:
            self._output.write(line + "\n")
            self._output.flush()
        except Exception:  # pragma: no cover
            self._logger.exception("failed to write telemetry record")
