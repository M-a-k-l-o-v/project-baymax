"""FakeBackend — canned responses + injectable failure modes for unit tests.

Per ADR 0011 §F1 (dedicated FakeBackend class over ad-hoc mocking) and
§F4 (injectable `warmup_delay_s` so tests can observe the /health 503→200
transition).

Design:
- Constructor takes lists of pre-built `PlanResult` / `InterpretResult`
  objects. Each call pops the next one (FIFO).
- `plan_task` / `interpret_results` can be configured to RAISE instead of
  returning — used to test the retry loop (transient failures) and the
  BackendError surfacing (persistent failures).
- `warmup_delay_s` simulates MLX cold-start; lets tests observe the
  /health gate.
- Does NOT use `_call_llm` — tests pointed at retry behavior instantiate
  FakeBackend, call its internal API directly, and assert on side effects.

Usage:
    backend = FakeBackend(
        model_id="fake-v1",
        plan_results=[PlanResult(...)],
        interpret_results=[InterpretResult(...)],
    )

    # Simulate a transient-then-succeed retry sequence:
    err_500 = _fake_http_error(500)
    backend = FakeBackend(
        model_id="fake-v1",
        plan_side_effects=[err_500, err_500, PlanResult(...)],  # succeed on 3rd attempt
    )
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from baymax.core.contracts import ToolCallStep
from baymax.service.inference import (
    InferenceBackend,
    InterpretRequest,
    InterpretResult,
    PlanRequest,
    PlanResult,
)


@dataclass
class _FakeHTTPError(Exception):
    """Minimal exception with `.status_code` so `is_retriable_api_error` classifies it."""

    status_code: int
    message: str = ""

    def __post_init__(self) -> None:
        super().__init__(self.message or f"HTTP {self.status_code}")


def make_http_error(status: int, message: str = "") -> _FakeHTTPError:
    """Build a fake HTTP-style exception. Useful for retry-loop tests."""
    return _FakeHTTPError(status_code=status, message=message)


class FakeBackend(InferenceBackend):
    """Backend fake with canned returns + configurable failure modes.

    Per ADR 0011 §F1 / §F4:
    - `plan_side_effects` / `interpret_side_effects`: FIFO queue of things
      to produce for successive calls. Each element is either a Result
      object (return normally) or an Exception (raise). Exhausting the
      queue raises `RuntimeError` — indicates the test set up too few
      responses.
    - `warmup_delay_s`: `warmup()` sleeps this long before returning.
      Tests use it to observe the /health gate; 0 = instant.
    - Attributes `plan_call_count` / `interpret_call_count` /
      `warmup_called` for assertions.
    """

    provider = "fake"
    cost_model = "amortized"
    max_context = 8192

    def __init__(
        self,
        model_id: str = "fake-v1",
        *,
        plan_side_effects: list[PlanResult | BaseException] | None = None,
        interpret_side_effects: list[InterpretResult | BaseException] | None = None,
        warmup_delay_s: float = 0.0,
        warmup_should_fail: BaseException | None = None,
    ) -> None:
        super().__init__(model_id=model_id)
        self._plan_queue: list[PlanResult | BaseException] = list(plan_side_effects or [])
        self._interpret_queue: list[InterpretResult | BaseException] = list(
            interpret_side_effects or []
        )
        self.warmup_delay_s = warmup_delay_s
        self.warmup_should_fail = warmup_should_fail
        self.plan_call_count = 0
        self.interpret_call_count = 0
        self.warmup_called = False

    async def warmup(self) -> None:
        self.warmup_called = True
        if self.warmup_delay_s > 0:
            await asyncio.sleep(self.warmup_delay_s)
        if self.warmup_should_fail is not None:
            raise self.warmup_should_fail

    async def plan_task(self, request: PlanRequest) -> PlanResult:
        self.plan_call_count += 1
        if not self._plan_queue:
            raise RuntimeError(
                f"FakeBackend.plan_task called {self.plan_call_count} times but no "
                f"plan_side_effects remain. Add more to the constructor."
            )
        item = self._plan_queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def interpret_results(self, request: InterpretRequest) -> InterpretResult:
        self.interpret_call_count += 1
        if not self._interpret_queue:
            raise RuntimeError(
                f"FakeBackend.interpret_results called {self.interpret_call_count} times but no "
                f"interpret_side_effects remain. Add more to the constructor."
            )
        item = self._interpret_queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


# ---------------------------------------------------------------------------
# Convenience builders — most tests want a minimally-populated Result.
# ---------------------------------------------------------------------------


def make_plan_result(
    *,
    plan: list[ToolCallStep] | None = None,
    intent_unclear: bool = False,
    clarification_question: str | None = None,
    refusal_reason: str | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
    cost_usd: float = 0.0,
) -> PlanResult:
    """Build a PlanResult with sane defaults for tests."""
    return PlanResult(
        plan=plan or [],
        intent_unclear=intent_unclear,
        request_type=None,
        request_complexity=None,
        clarification_question=clarification_question,
        refusal_reason=refusal_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


def make_interpret_result(
    *,
    text: str = "Done.",
    input_tokens: int = 10,
    output_tokens: int = 3,
    cost_usd: float = 0.0,
) -> InterpretResult:
    """Build an InterpretResult with sane defaults."""
    return InterpretResult(
        response_text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


# Silence unused-import warnings for symbols re-exported for test convenience.
_reexports: tuple[Any, ...] = (field,)
