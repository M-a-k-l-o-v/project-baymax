"""Tool dispatcher — routes ToolCallStep → fake adapter method → ToolCallResult.

The agent core uses a `ToolDispatcher` callable (defined in agent.py) to
execute tool calls. This module provides a concrete implementation that
routes by tool namespace (calendar.*, notion.*, gmail.*, clipboard.*) to
the corresponding fake adapter from Ronin's `baymax.tools.fake_*` modules.

When real adapters arrive in v2, swap this module's per-namespace bindings
for real-API adapter instances. The agent core doesn't change.
"""

from __future__ import annotations

from typing import Any

from baymax.core.contracts import ToolCallResult, ToolCallStep

# DECISION: import the fake adapters lazily inside the constructor so that
# (a) unit tests for this module can mock the imports, and (b) the dispatcher
# raises a clear error if the fake-adapter package is missing rather than
# at import time of unrelated modules.


class FakeAdapterDispatcher:
    """Routes tool calls to Ronin's in-memory fake adapters.

    Constructed once per request (so per-request state is isolated). State
    flows in via `initial_state` and can be read back via `export_state()`
    after dispatching, useful for the eval to verify expected state changes.
    """

    def __init__(self, initial_state: dict[str, Any] | None = None) -> None:
        # DECISION: lazy import inside __init__ — see module docstring above.
        from baymax.tools.fake_calendar import FakeCalendarAdapter
        from baymax.tools.fake_clipboard import FakeClipboardAdapter
        from baymax.tools.fake_gmail import FakeGmailAdapter
        from baymax.tools.fake_notion import FakeNotionAdapter

        state = initial_state or {}
        self._calendar = FakeCalendarAdapter.from_initial_state(state)
        self._notion = FakeNotionAdapter.from_initial_state(state)
        self._gmail = FakeGmailAdapter.from_initial_state(state)
        self._clipboard = FakeClipboardAdapter.from_initial_state(state)

    async def __call__(self, step: ToolCallStep) -> ToolCallResult:
        """Dispatch one step. Returns ToolCallResult (mirrors FakeToolResult shape)."""
        # DECISION: split tool name on "." — first segment = namespace, rest = method.
        # If the model emits a tool name we don't know, return a failure rather
        # than raising — the agent loop handles result.success == False as a step
        # failure, which is the right semantics.
        if "." not in step.tool:
            return ToolCallResult(
                success=False,
                tool=step.tool,
                error=f"tool name '{step.tool}' is not namespaced (expected 'ns.method')",
            )

        namespace, method_name = step.tool.split(".", maxsplit=1)
        adapter = self._adapter_for(namespace)
        if adapter is None:
            return ToolCallResult(
                success=False,
                tool=step.tool,
                error=f"no adapter registered for namespace '{namespace}'",
            )

        method = getattr(adapter, method_name, None)
        if method is None or not callable(method):
            return ToolCallResult(
                success=False,
                tool=step.tool,
                error=f"adapter for '{namespace}' has no method '{method_name}'",
            )

        # DECISION: fake adapters use keyword-only arguments. Forward the step's
        # arguments dict as **kwargs. If the model emitted unknown kwargs, Python
        # raises TypeError, which we convert into a ToolCallResult failure (so
        # the agent loop can attribute the failure to this step).
        try:
            # Fake adapter methods are sync. Wrap in try/except to surface as
            # ToolCallResult failure rather than bubbling exceptions.
            fake_result = method(**step.arguments)
        except Exception as exc:
            return ToolCallResult(
                success=False,
                tool=step.tool,
                error=f"{type(exc).__name__}: {exc}",
            )

        return _convert_fake_result(fake_result, fallback_tool=step.tool)

    def _adapter_for(self, namespace: str) -> Any | None:
        """Look up the adapter instance for a tool namespace."""
        return {
            "calendar": self._calendar,
            "notion": self._notion,
            "gmail": self._gmail,
            "clipboard": self._clipboard,
        }.get(namespace)

    def export_state(self) -> dict[str, Any]:
        """Return the merged current state across all adapters.

        Useful for the eval harness to verify expected state changes after
        dispatching, or for debugging via telemetry.
        """
        state: dict[str, Any] = {}
        state.update(self._calendar.export_state())
        state.update(self._notion.export_state())
        state.update(self._gmail.export_state())
        state.update(self._clipboard.export_state())
        return state


def _convert_fake_result(fake_result: Any, *, fallback_tool: str) -> ToolCallResult:
    """Convert FakeToolResult (from baymax.tools.fake_base) → ToolCallResult.

    Defensive: works even if the fake adapter returns something unexpected —
    surface as failure rather than crash.
    """
    # DECISION: duck-type on fields rather than isinstance check, so the
    # dispatcher works with any object that has the expected shape (useful
    # for testing with stubs).
    success = getattr(fake_result, "success", None)
    tool = getattr(fake_result, "tool", fallback_tool)
    error = getattr(fake_result, "error", None)
    data = getattr(fake_result, "data", None)

    if success is None:
        return ToolCallResult(
            success=False,
            tool=fallback_tool,
            error=f"adapter returned unexpected shape: {type(fake_result).__name__}",
        )

    return ToolCallResult(
        success=bool(success),
        tool=str(tool),
        error=str(error) if error is not None else None,
        data=dict(data) if isinstance(data, dict) else {},
    )
