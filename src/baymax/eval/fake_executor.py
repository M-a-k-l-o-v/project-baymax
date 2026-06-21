"""Execute agent tool calls against fake adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from baymax.eval.scorer import AgentToolCall
from baymax.tools.fake_base import FakeToolResult
from baymax.tools.fake_calendar import FakeCalendarAdapter
from baymax.tools.fake_clipboard import FakeClipboardAdapter
from baymax.tools.fake_gmail import FakeGmailAdapter
from baymax.tools.fake_notion import FakeNotionAdapter


class FakeExecutionResult(BaseModel):
    """Result of executing a sequence of fake tool calls."""

    model_config = ConfigDict(extra="forbid")

    tool_results: list[FakeToolResult] = Field(default_factory=list)
    final_state: dict[str, Any]


class FakeToolExecutor:
    """Routes tool calls to fake adapters backed by shared initial state."""

    def __init__(self, initial_state: dict[str, Any]) -> None:
        self._calendar = FakeCalendarAdapter.from_initial_state(initial_state)
        self._notion = FakeNotionAdapter.from_initial_state(initial_state)
        self._gmail = FakeGmailAdapter.from_initial_state(initial_state)
        self._clipboard = FakeClipboardAdapter.from_initial_state(initial_state)

    def execute(self, tool_calls: list[AgentToolCall]) -> FakeExecutionResult:
        tool_results = [self._execute_one(tool_call) for tool_call in tool_calls]
        return FakeExecutionResult(
            tool_results=tool_results,
            final_state=self.export_state(),
        )

    def export_state(self) -> dict[str, Any]:
        return {
            **self._calendar.export_state(),
            **self._notion.export_state(),
            **self._gmail.export_state(),
            **self._clipboard.export_state(),
        }

    def _execute_one(self, tool_call: AgentToolCall) -> FakeToolResult:
        try:
            return self._dispatch(tool_call)
        except TypeError as error:
            return FakeToolResult(
                success=False,
                tool=tool_call.tool,
                error=f"invalid arguments for {tool_call.tool}: {error}",
            )
        except ValidationError as error:
            return FakeToolResult(
                success=False,
                tool=tool_call.tool,
                error=f"validation failed for {tool_call.tool}: {error}",
            )

    def _dispatch(self, tool_call: AgentToolCall) -> FakeToolResult:
        arguments = tool_call.arguments

        if tool_call.tool == "calendar.create_event":
            return self._calendar.create_event(**arguments)
        if tool_call.tool == "calendar.update_event":
            return self._calendar.update_event(**arguments)
        if tool_call.tool == "notion.create_task":
            return self._notion.create_task(**arguments)
        if tool_call.tool == "notion.update_task":
            return self._notion.update_task(**arguments)
        if tool_call.tool == "gmail.create_draft":
            return self._gmail.create_draft(**arguments)
        if tool_call.tool == "gmail.send_email":
            return self._gmail.send_email(**arguments)
        if tool_call.tool == "clipboard.read":
            return self._clipboard.read()
        if tool_call.tool == "clipboard.write":
            return self._clipboard.write(**arguments)

        return FakeToolResult(
            success=False,
            tool=tool_call.tool,
            error=f"unknown fake tool: {tool_call.tool}",
        )


def execute_tool_calls(
    *,
    initial_state: dict[str, Any],
    tool_calls: list[AgentToolCall],
) -> FakeExecutionResult:
    """Execute tool calls against fake adapters and return final state."""

    executor = FakeToolExecutor(initial_state)
    return executor.execute(tool_calls)
