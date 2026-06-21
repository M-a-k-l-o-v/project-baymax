"""Fake Calendar adapter for deterministic eval runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from baymax.tools.fake_base import FakeToolResult


class CalendarEvent(BaseModel):
    """Calendar event stored in the fake adapter state."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    start_date: str
    start_time: str
    duration_minutes: int = Field(gt=0)


class FakeCalendarAdapter:
    """In-memory Calendar adapter backed by scenario state."""

    def __init__(self, events: list[CalendarEvent] | None = None) -> None:
        self._events = list(events or [])

    @classmethod
    def from_initial_state(cls, initial_state: dict[str, Any]) -> FakeCalendarAdapter:
        raw_events = initial_state.get("calendar_events", [])
        events = [CalendarEvent.model_validate(event) for event in raw_events]
        return cls(events=events)

    def export_state(self) -> dict[str, Any]:
        return {"calendar_events": [event.model_dump(mode="json") for event in self._events]}

    def create_event(
        self,
        *,
        title: str,
        start_date: str,
        start_time: str,
        duration_minutes: int,
    ) -> FakeToolResult:
        event = CalendarEvent(
            id=self._next_event_id(),
            title=title,
            start_date=start_date,
            start_time=start_time,
            duration_minutes=duration_minutes,
        )
        self._events.append(event)
        return FakeToolResult(
            success=True,
            tool="calendar.create_event",
            data={"event_id": event.id},
        )

    def update_event(
        self,
        *,
        event_id: str,
        title: str | None = None,
        start_date: str | None = None,
        start_time: str | None = None,
        duration_minutes: int | None = None,
    ) -> FakeToolResult:
        event_index = self._find_event_index(event_id)
        if event_index is None:
            return FakeToolResult(
                success=False,
                tool="calendar.update_event",
                error=f"calendar event not found: {event_id}",
            )

        existing_event = self._events[event_index]
        self._events[event_index] = CalendarEvent.model_validate(
            {
                **existing_event.model_dump(mode="json"),
                **{
                    key: value
                    for key, value in {
                        "title": title,
                        "start_date": start_date,
                        "start_time": start_time,
                        "duration_minutes": duration_minutes,
                    }.items()
                    if value is not None
                },
            }
        )
        return FakeToolResult(success=True, tool="calendar.update_event")

    def _find_event_index(self, event_id: str) -> int | None:
        for index, event in enumerate(self._events):
            if event.id == event_id:
                return index
        return None

    def _next_event_id(self) -> str:
        existing_ids = {event.id for event in self._events}
        next_index = len(self._events) + 1
        while True:
            candidate_id = f"evt_fake_calendar_{next_index:03}"
            if candidate_id not in existing_ids:
                return candidate_id
            next_index += 1
