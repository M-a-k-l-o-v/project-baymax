"""Fake system clipboard adapter for deterministic eval runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from baymax.tools.fake_base import FakeToolResult


class ClipboardState(BaseModel):
    """System clipboard state used by the fake adapter."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""


class FakeClipboardAdapter:
    """In-memory system clipboard adapter backed by scenario state."""

    def __init__(self, state: ClipboardState | None = None) -> None:
        self._state = state or ClipboardState()

    @classmethod
    def from_initial_state(cls, initial_state: dict[str, Any]) -> FakeClipboardAdapter:
        raw_clipboard = initial_state.get("clipboard", {})
        state = ClipboardState.model_validate(raw_clipboard)
        return cls(state=state)

    def export_state(self) -> dict[str, Any]:
        return {"clipboard": self._state.model_dump(mode="json")}

    def read(self) -> FakeToolResult:
        return FakeToolResult(
            success=True,
            tool="clipboard.read",
            data={"text": self._state.text},
        )

    def write(self, *, text: str) -> FakeToolResult:
        self._state = ClipboardState(text=text)
        return FakeToolResult(success=True, tool="clipboard.write")
