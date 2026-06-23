"""Tests for baymax.telemetry.logger."""

from __future__ import annotations

import io
import json

from baymax.telemetry.logger import CostAccumulator, TelemetryLogger, _redact


def test_redact_strips_sensitive_fields():
    raw = {
        "user": "alice",
        "api_key": "secret123",
        "nested": {"authorization": "Bearer xyz", "ok": "fine"},
        "list_field": [{"token": "abc"}, "plain"],
    }
    out = _redact(raw)
    assert out["user"] == "alice"
    assert out["api_key"] == "***REDACTED***"
    assert out["nested"]["authorization"] == "***REDACTED***"
    assert out["nested"]["ok"] == "fine"
    assert out["list_field"][0]["token"] == "***REDACTED***"
    assert out["list_field"][1] == "plain"


def test_cost_accumulator_aggregates():
    cost = CostAccumulator()
    cost.add_llm(input_tokens=100, output_tokens=20, usd=0.001)
    cost.add_llm(input_tokens=50, output_tokens=10, usd=0.0005)
    cost.add_tool_call()
    cost.add_tool_call()
    assert cost.input_tokens == 150
    assert cost.output_tokens == 30
    assert cost.tool_call_count == 2
    assert abs(cost.usd - 0.0015) < 1e-9


def test_telemetry_trace_writes_events_and_summary():
    buffer = io.StringIO()
    logger = TelemetryLogger(output_stream=buffer)
    with logger.trace("test_root", extra_field="hello") as trace:
        trace.task_id = "run_42.1.0"
        logger.event(trace, "step_one", value=1)
        trace.cost.add_llm(input_tokens=10, output_tokens=5, usd=0.0001)
    output_lines = [json.loads(line) for line in buffer.getvalue().strip().split("\n")]
    # We expect: root started, step_one, root completed, trace_summary
    assert len(output_lines) >= 3
    events = [r["event"] for r in output_lines]
    assert "test_root" in events
    assert "step_one" in events
    assert "trace_summary" in events
    summary = next(r for r in output_lines if r["event"] == "trace_summary")
    assert summary["task_id"] == "run_42.1.0"
    assert summary["input_tokens"] == 10
    assert summary["cost_usd"] == 0.0001


def test_telemetry_redacts_sensitive_event_fields():
    buffer = io.StringIO()
    logger = TelemetryLogger(output_stream=buffer)
    with logger.trace("test_root") as trace:
        logger.event(trace, "secret_event", api_key="should-not-appear")
    output = buffer.getvalue()
    assert "should-not-appear" not in output
    assert "***REDACTED***" in output
