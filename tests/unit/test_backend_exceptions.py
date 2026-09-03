"""Tests for exceptions module (ADR 0011 §E1, §D3, §D4)."""

from __future__ import annotations

import pytest

from baymax.core.exceptions import (
    BackendConfigError,
    BackendError,
    IncompleteRegistryEntry,
    ModelNotFound,
    RetryAttempt,
    WarmupFailure,
    WarmupTimeout,
    is_retriable_api_error,
)
from tests.fakes.backend import make_http_error

# ---------------------------------------------------------------------------
# BackendError shape.
# ---------------------------------------------------------------------------


def test_backend_error_preserves_underlying_and_attempts() -> None:
    orig = RuntimeError("connection reset")
    history = [
        RetryAttempt(attempt=1, delay_before_ms=1000, cause="http_500", underlying_repr=repr(orig)),
        RetryAttempt(attempt=2, delay_before_ms=2000, cause="http_500", underlying_repr=repr(orig)),
    ]
    err = BackendError(
        kind="retry_exhausted",
        message="openai backend failed after 2 attempt(s): http_500",
        underlying=orig,
        attempts_history=history,
        backend="openai",
    )
    assert err.kind == "retry_exhausted"
    assert err.underlying is orig
    assert len(err.attempts_history) == 2
    assert err.backend == "openai"
    # Message-through-str.
    assert "openai backend failed after 2 attempt(s)" in str(err)


def test_backend_error_default_attempts_history_is_empty_list() -> None:
    err = BackendError(kind="non_retriable", message="x")
    assert err.attempts_history == []


def test_backend_error_repr_summarises() -> None:
    err = BackendError(kind="non_retriable", message="msg", backend="mlx")
    r = repr(err)
    assert "kind='non_retriable'" in r
    assert "backend='mlx'" in r


# ---------------------------------------------------------------------------
# WarmupFailure / WarmupTimeout.
# ---------------------------------------------------------------------------


def test_warmup_failure_stage_and_cause_in_message() -> None:
    err = WarmupFailure(stage="load_model_weights", cause="Weights missing", hint="check path")
    assert "load_model_weights" in str(err)
    assert "Weights missing" in str(err)
    assert "check path" in str(err)


def test_warmup_timeout_reports_elapsed_and_timeout() -> None:
    err = WarmupTimeout(elapsed_s=125.4, timeout_s=120.0)
    assert err.stage == "warmup_timeout"
    assert err.elapsed_s == pytest.approx(125.4)
    assert err.timeout_s == pytest.approx(120.0)
    assert "125" in str(err)


# ---------------------------------------------------------------------------
# Registry exceptions.
# ---------------------------------------------------------------------------


def test_model_not_found_message_includes_id_and_path() -> None:
    err = ModelNotFound(model_id="qwen-1.5b-baymax-v99", registry_path="models/models.json")
    assert "qwen-1.5b-baymax-v99" in str(err)
    assert "models/models.json" in str(err)


def test_incomplete_registry_entry_message_lists_missing_fields() -> None:
    err = IncompleteRegistryEntry(model_id="broken", missing_fields=["config_hash", "trained_at"])
    assert "broken" in str(err)
    assert "config_hash" in str(err)
    assert "trained_at" in str(err)


def test_backend_config_error_names_missing_var() -> None:
    err = BackendConfigError(backend="openai", missing="OPENAI_API_KEY", hint="See .env.example.")
    assert "openai" in str(err)
    assert "OPENAI_API_KEY" in str(err)
    assert ".env.example" in str(err)


# ---------------------------------------------------------------------------
# is_retriable_api_error classifier — per §D3 / §D4.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_retriable_http_statuses_are_retried(status: int) -> None:
    retriable, cause = is_retriable_api_error(make_http_error(status))
    assert retriable is True
    assert cause == f"http_{status}"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_non_retriable_http_statuses_are_not_retried(status: int) -> None:
    retriable, cause = is_retriable_api_error(make_http_error(status))
    assert retriable is False
    assert cause == f"http_{status}"


def test_unknown_http_status_defaults_to_non_retriable() -> None:
    retriable, cause = is_retriable_api_error(make_http_error(418))  # I'm a teapot
    assert retriable is False
    assert cause == "http_418_unclassified"


def test_connection_errors_are_retriable() -> None:
    retriable, cause = is_retriable_api_error(ConnectionResetError("nope"))
    assert retriable is True
    assert "connection" in cause


def test_arbitrary_exceptions_are_non_retriable() -> None:
    """A raw ValueError has no HTTP status and isn't a known transport error — fail fast."""
    retriable, cause = is_retriable_api_error(ValueError("bad input"))
    assert retriable is False
    assert cause.startswith("unknown_")


def test_openai_style_response_status_is_read() -> None:
    """Some SDKs expose status on `.response.status_code` instead of top-level."""

    class _FakeOpenAIError(Exception):
        def __init__(self) -> None:
            super().__init__("rate limit")
            self.response = type("R", (), {"status_code": 429})()

    retriable, cause = is_retriable_api_error(_FakeOpenAIError())
    assert retriable is True
    assert cause == "http_429"
