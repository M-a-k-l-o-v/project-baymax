"""Custom exceptions for BAYMAX runtime.

Per ADR 0011 §6 — backend failures raise `BackendError` (wraps underlying).
The agent catches this single type and maps to `ErrorType.BACKEND_ERROR` on
the `AgentResponse` (per E2). Consumers who need forensic detail read
`.underlying` and `.attempts_history`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetryAttempt:
    """One entry in a backend retry sequence."""

    attempt: int
    delay_before_ms: int
    cause: str  # short classification (e.g., "rate_limit_429", "connection_timeout")
    underlying_repr: str  # str(exc) for the failed attempt


class BackendError(Exception):
    """Uniform backend failure — wraps any underlying exception.

    Raised by `InferenceBackend._call_llm` when a retry sequence exhausts,
    OR when a non-retriable error is encountered, OR when an MLX-side
    deterministic failure occurs.

    The Agent catches ONE exception type across all backends (uniformity
    principle per ADR 0011 §Reasoning). Forensic detail is preserved in
    `underlying` + `attempts_history`.
    """

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        underlying: BaseException | None = None,
        attempts_history: list[RetryAttempt] | None = None,
        backend: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.underlying = underlying
        self.attempts_history: list[RetryAttempt] = attempts_history or []
        self.backend = backend

    def __repr__(self) -> str:
        return (
            f"BackendError(kind={self.kind!r}, backend={self.backend!r}, "
            f"attempts={len(self.attempts_history)}, "
            f"underlying={self.underlying!r})"
        )


@dataclass
class WarmupFailure(Exception):
    """Backend warmup failed. Startup-fatal per ADR 0011 §C3 (fail-loud).

    Raised during FastAPI lifespan warmup. When raised, uvicorn exits;
    `/health` never becomes ready.

    Stage identifiers help distinguish failure modes so operators can
    diagnose without reading a traceback:
    - "load_warmup_scenario" — JSON file missing / malformed
    - "load_model_weights" — checkpoint path missing or corrupt
    - "tokenize" — tokenizer config missing / mismatched
    - "generate" — inference call itself failed (model incompatible, OOM, etc.)
    """

    stage: str
    cause: str
    hint: str = ""
    underlying: BaseException | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # `Exception.__init__` populates `.args` for str() / logging.
        super().__init__(
            f"[{self.stage}] {self.cause}" + (f" | hint: {self.hint}" if self.hint else "")
        )


class WarmupTimeout(WarmupFailure):
    """Warmup exceeded the hard timeout (120s per ADR 0011 §C4)."""

    def __init__(self, elapsed_s: float, timeout_s: float) -> None:
        super().__init__(
            stage="warmup_timeout",
            cause=f"Warmup exceeded {timeout_s:.0f}s (elapsed: {elapsed_s:.1f}s)",
            hint=(
                "Likely: model weights too large for memory, MLX version mismatch, "
                "or infinite loop in generation."
            ),
        )
        self.elapsed_s = elapsed_s
        self.timeout_s = timeout_s


class ModelNotFound(Exception):
    """Registry lookup failed — the requested model_id has no entry in models.json."""

    def __init__(self, model_id: str, registry_path: str) -> None:
        super().__init__(
            f"Model {model_id!r} not found in registry at {registry_path}. "
            f"Check models/models.json — is the id spelled correctly and the entry committed?"
        )
        self.model_id = model_id
        self.registry_path = registry_path


class IncompleteRegistryEntry(Exception):
    """Registry entry exists but is missing required fields (per ADR 0012 §2)."""

    def __init__(self, model_id: str, missing_fields: list[str]) -> None:
        super().__init__(
            f"Registry entry for {model_id!r} is missing required fields: {missing_fields}. "
            f"Required per ADR 0012 §2: id, base, adapter_path, trained_at, config_hash."
        )
        self.model_id = model_id
        self.missing_fields = missing_fields


class BackendConfigError(Exception):
    """Backend construction failed — missing env var, bad config, etc.

    Raised in `Backend.__init__` per ADR 0011 §B4 (backend fetches own env
    vars, raises loud on missing). Surfaces at lifespan startup per §B5.
    """

    def __init__(self, backend: str, missing: str, hint: str = "") -> None:
        super().__init__(
            f"{backend} backend requires {missing}. "
            + (hint if hint else f"Set {missing} in the environment.")
        )
        self.backend = backend
        self.missing = missing


# ---------------------------------------------------------------------------
# Error classification helper (used by base-class retry logic)
# ---------------------------------------------------------------------------


# Retriable HTTP status codes for API-backed backends (per ADR 0011 §D3).
RETRIABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

# Non-retriable HTTP status codes — client-side, retry won't help (per §D4).
NON_RETRIABLE_HTTP_STATUSES = frozenset({400, 401, 403, 404, 422})


def is_retriable_api_error(exc: BaseException) -> tuple[bool, str]:
    """Classify an API-backend exception as retriable or not.

    Returns (retriable, cause_label). `cause_label` is a short kebab/snake
    identifier used in retry-telemetry events so consumers can filter by
    cause without re-inspecting the exception.

    Called by the base-class `_call_llm` retry loop. MLX backends do NOT
    call this — MLX errors are always non-retriable per ADR 0011 §D3.
    """
    # Network-level transient errors (retry).
    exc_name = type(exc).__name__
    if exc_name in {
        "ConnectionResetError",
        "ConnectTimeoutError",
        "TimeoutError",
        "ReadTimeoutError",
    }:
        return True, f"connection_{exc_name.lower()}"

    # HTTP status inspection — try common attribute names used by
    # httpx / requests / openai / anthropic SDKs.
    status: int | None = None
    for attr in ("status_code", "status", "response_status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            status = val
            break
    # openai SDK: exc.response is the httpx.Response; status_code hangs off it.
    if status is None:
        resp = getattr(exc, "response", None)
        if resp is not None:
            val = getattr(resp, "status_code", None)
            if isinstance(val, int):
                status = val

    if status is not None:
        if status in RETRIABLE_HTTP_STATUSES:
            return True, f"http_{status}"
        if status in NON_RETRIABLE_HTTP_STATUSES:
            return False, f"http_{status}"
        # Unknown status — err on side of non-retriable (fail loud).
        return False, f"http_{status}_unclassified"

    # No HTTP status and not a known connection error — non-retriable by default.
    return False, f"unknown_{exc_name}"


def _describe_exception(exc: BaseException) -> dict[str, Any]:
    """Compact dict describing an exception for telemetry."""
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }
