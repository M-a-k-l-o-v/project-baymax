"""Retry loop tests for `InferenceBackend._call_llm` (ADR 0011 §D).

Covers:
- Success on first attempt (no retry noise)
- Success on Nth attempt (transient retriable failures then success)
- Retry exhaustion → BackendError kind="retry_exhausted"
- Non-retriable failure → BackendError kind="non_retriable" (no retries consumed)
- Backoff off-by-one behaviour (1s first-wait, not 2s)
- MLX-style classifier disables retry entirely
- Telemetry events emitted per-attempt AND final aggregate
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from baymax.core.exceptions import BackendError, RetryAttempt, is_retriable_api_error
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
    _compute_backoff_delay_s,
)
from tests.fakes.backend import FakeBackend, make_http_error, make_plan_result


class _RetryHarness(InferenceBackend):
    """Minimal InferenceBackend to exercise _call_llm directly."""

    provider = "test-retry"

    def __init__(self, model_id: str = "harness") -> None:
        super().__init__(model_id=model_id)

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        raise NotImplementedError  # not exercised here

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        raise NotImplementedError


@pytest.fixture
def harness() -> _RetryHarness:
    return _RetryHarness()


@pytest.fixture(autouse=True)
def _patch_sleep():
    """Patch asyncio.sleep so retry backoff doesn't stall the test suite (per ADR 0011 §F3)."""
    with patch("baymax.service.inference.asyncio.sleep", new=_noop_sleep):
        yield


async def _noop_sleep(_delay: float) -> None:  # pragma: no cover — trivial
    return


# ---------------------------------------------------------------------------
# Success paths.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_llm_returns_on_first_attempt(harness: _RetryHarness) -> None:
    call_count = 0

    async def _do_call() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await harness._call_llm(_do_call)
    assert result == "ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_call_llm_succeeds_on_third_attempt_after_transient_429s(
    harness: _RetryHarness,
) -> None:
    """Two transient 429s then success — result returned, no BackendError."""
    call_count = 0

    async def _do_call() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise make_http_error(429)
        return "success"

    result = await harness._call_llm(_do_call)
    assert result == "success"
    assert call_count == 3


# ---------------------------------------------------------------------------
# Failure paths.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_llm_raises_backend_error_when_retries_exhausted(harness: _RetryHarness) -> None:
    """Three straight 500s → BackendError.kind == 'retry_exhausted'."""

    async def _do_call() -> str:
        raise make_http_error(500)

    with pytest.raises(BackendError) as exc_info:
        await harness._call_llm(_do_call)

    err = exc_info.value
    assert err.kind == "retry_exhausted"
    assert err.backend == "test-retry"
    assert len(err.attempts_history) == 3
    # Each attempt should carry the classifier's cause label.
    for attempt_record in err.attempts_history:
        assert attempt_record.cause == "http_500"
    # Original exception preserved for forensics.
    assert isinstance(err.underlying, Exception)


@pytest.mark.asyncio
async def test_call_llm_raises_immediately_on_non_retriable(harness: _RetryHarness) -> None:
    """HTTP 401 = client-side; must NOT retry (§D4)."""
    call_count = 0

    async def _do_call() -> str:
        nonlocal call_count
        call_count += 1
        raise make_http_error(401)

    with pytest.raises(BackendError) as exc_info:
        await harness._call_llm(_do_call)

    err = exc_info.value
    assert err.kind == "non_retriable"
    assert call_count == 1  # single attempt, no retry
    assert len(err.attempts_history) == 1
    assert err.attempts_history[0].cause == "http_401"


@pytest.mark.asyncio
async def test_call_llm_mlx_classifier_disables_retry(harness: _RetryHarness) -> None:
    """A classifier that always returns (False, ...) mirrors MLX behaviour: no retry ever (§D3)."""
    call_count = 0

    async def _do_call() -> str:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("metal OOM")

    def _mlx_classifier(_exc: BaseException) -> tuple[bool, str]:
        return False, "mlx_deterministic"

    with pytest.raises(BackendError) as exc_info:
        await harness._call_llm(_do_call, retriable_classifier=_mlx_classifier)

    assert call_count == 1  # no retry
    assert exc_info.value.kind == "non_retriable"
    assert exc_info.value.attempts_history[0].cause == "mlx_deterministic"


# ---------------------------------------------------------------------------
# Backoff math (off-by-one regression guard).
# ---------------------------------------------------------------------------


def test_backoff_first_wait_is_around_one_second_not_two() -> None:
    """attempt=1 (first-failed) should schedule ~1s (base * 2^0), not 2s (base * 2^1).

    Regression guard for the off-by-one bug fixed 2026-08-26: earlier code did
    `factor ** attempt` which made the first wait 2s. Correct spec per ADR 0011
    §D2 is 1s, 2s, 4s.
    """
    # With ±25% jitter, attempt=1 delay ∈ [0.75, 1.25]s.
    for _ in range(20):
        delay = _compute_backoff_delay_s(1)
        assert 0.7 <= delay <= 1.3, f"attempt=1 delay {delay}s out of expected 1s±25% band"


def test_backoff_second_wait_is_around_two_seconds() -> None:
    for _ in range(20):
        delay = _compute_backoff_delay_s(2)
        assert 1.4 <= delay <= 2.6, f"attempt=2 delay {delay}s out of expected 2s±25% band"


def test_backoff_third_wait_is_around_four_seconds() -> None:
    for _ in range(20):
        delay = _compute_backoff_delay_s(3)
        assert 2.8 <= delay <= 5.2, f"attempt=3 delay {delay}s out of expected 4s±25% band"


# ---------------------------------------------------------------------------
# Telemetry — per-attempt + final aggregate (§D5).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telemetry_emits_per_attempt_and_final_success(
    harness: _RetryHarness, caplog: pytest.LogCaptureFixture
) -> None:
    """Success path emits attempt event(s) + a single backend_call_complete."""

    async def _do_call() -> str:
        return "ok"

    with caplog.at_level("INFO", logger="baymax.backend"):
        await harness._call_llm(_do_call, telemetry_kind="test_success")

    attempt_events = [r for r in caplog.records if getattr(r, "event", None) == "backend_attempt"]
    complete_events = [
        r for r in caplog.records if getattr(r, "event", None) == "backend_call_complete"
    ]
    assert len(attempt_events) == 1
    assert len(complete_events) == 1
    assert complete_events[0].__dict__["final_status"] == "success"


@pytest.mark.asyncio
async def test_telemetry_emits_retry_event_on_transient_failure(
    harness: _RetryHarness, caplog: pytest.LogCaptureFixture
) -> None:
    call_count = 0

    async def _do_call() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise make_http_error(503)
        return "ok"

    with caplog.at_level("INFO", logger="baymax.backend"):
        await harness._call_llm(_do_call)

    retry_events = [r for r in caplog.records if getattr(r, "event", None) == "backend_retry"]
    assert len(retry_events) == 1
    assert retry_events[0].__dict__["cause"] == "http_503"


@pytest.mark.asyncio
async def test_telemetry_final_aggregate_reports_failed_status(
    harness: _RetryHarness, caplog: pytest.LogCaptureFixture
) -> None:
    async def _do_call() -> str:
        raise make_http_error(500)

    with caplog.at_level("INFO", logger="baymax.backend"):
        with pytest.raises(BackendError):
            await harness._call_llm(_do_call)

    complete_events = [
        r for r in caplog.records if getattr(r, "event", None) == "backend_call_complete"
    ]
    assert len(complete_events) == 1
    final = complete_events[0].__dict__
    assert final["final_status"] == "failed"
    assert final["failure_kind"] == "retry_exhausted"
    assert final["total_attempts"] == 3


# ---------------------------------------------------------------------------
# FakeBackend basic behaviour (for later test authors reference).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_backend_returns_queued_plan_results() -> None:
    plan_a = make_plan_result()
    plan_b = make_plan_result()
    backend = FakeBackend(plan_side_effects=[plan_a, plan_b])

    request = PlanRequest(user_input="x", available_tools=["t"], context={}, tool_schemas={})
    assert await backend.plan_task(request) is plan_a
    assert await backend.plan_task(request) is plan_b
    assert backend.plan_call_count == 2


@pytest.mark.asyncio
async def test_fake_backend_raises_when_queue_exhausted() -> None:
    backend = FakeBackend(plan_side_effects=[make_plan_result()])
    request = PlanRequest(user_input="x", available_tools=["t"], context={}, tool_schemas={})
    await backend.plan_task(request)
    with pytest.raises(RuntimeError, match="no plan_side_effects remain"):
        await backend.plan_task(request)


# Silence unused-import warning for symbols only used in typing contexts.
_ = (Any, RetryAttempt, InterpretResult, is_retriable_api_error, asyncio)
