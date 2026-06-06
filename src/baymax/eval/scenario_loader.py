"""Load and validate BAYMAX evaluation scenarios."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScenarioCategory = Literal["calendar", "notion", "gmail", "clipboard", "multi_tool"]
ScenarioDifficulty = Literal["explicit", "implicit", "contextual", "ambiguous", "multi_step"]


class ToolCallExpectedBehavior(BaseModel):
    """Expected behavior for scenarios where the agent should call one tool."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_call"]
    tool: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    arguments: dict[str, Any]


class ClarificationExpectedBehavior(BaseModel):
    """Expected behavior for scenarios where the agent should ask a question."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["clarification"]
    question_contains: list[str] = Field(min_length=1)

    @field_validator("question_contains")
    @classmethod
    def question_contains_must_be_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("question_contains entries must be unique")
        return values


class RefusalExpectedBehavior(BaseModel):
    """Expected behavior for scenarios where the agent should refuse."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["refusal"]
    reason_contains: list[str] = Field(min_length=1)

    @field_validator("reason_contains")
    @classmethod
    def reason_contains_must_be_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("reason_contains entries must be unique")
        return values


ExpectedBehavior = Annotated[
    ToolCallExpectedBehavior | ClarificationExpectedBehavior | RefusalExpectedBehavior,
    Field(discriminator="type"),
]


class Scenario(BaseModel):
    """A scripted eval scenario loaded from ``scenarios/v1``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*_[0-9]{3}$")
    category: ScenarioCategory
    difficulty: ScenarioDifficulty
    description: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    current_time: datetime
    audio_path: str | None = None
    available_tools: list[str] = Field(min_length=1)
    initial_state: dict[str, Any]
    expected_behavior: ExpectedBehavior
    success_criteria: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("available_tools")
    @classmethod
    def available_tools_must_be_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("available_tools entries must be unique")
        return values

    @field_validator("success_criteria")
    @classmethod
    def success_criteria_must_be_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("success_criteria entries must be unique")
        return values

    @field_validator("tags")
    @classmethod
    def tags_must_be_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("tags entries must be unique")
        return values


def load_scenario(path: Path) -> Scenario:
    """Load and validate one scenario JSON file."""

    with path.open(encoding="utf-8") as scenario_file:
        raw_scenario = json.load(scenario_file)
    return Scenario.model_validate(raw_scenario)


def load_scenarios(directory: Path) -> list[Scenario]:
    """Load and validate all scenario JSON files in a directory."""

    scenario_paths = sorted(directory.glob("*.json"))
    return [load_scenario(path) for path in scenario_paths]
