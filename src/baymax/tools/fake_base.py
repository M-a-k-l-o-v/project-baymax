"""Shared primitives for fake tool adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FakeToolResult(BaseModel):
    """Result returned by a fake tool call."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    tool: str
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
