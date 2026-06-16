import pytest
from pydantic import ValidationError

from baymax.tools.fake_calendar import FakeCalendarAdapter


def test_create_event_appends_event_to_fake_state() -> None:
    adapter = FakeCalendarAdapter.from_initial_state({"calendar_events": []})

    result = adapter.create_event(
        title="Linear algebra revision",
        start_date="2026-05-19",
        start_time="16:00",
        duration_minutes=120,
    )

    assert result.success is True
    assert result.tool == "calendar.create_event"
    assert adapter.export_state() == {
        "calendar_events": [
            {
                "id": "evt_fake_calendar_001",
                "title": "Linear algebra revision",
                "start_date": "2026-05-19",
                "start_time": "16:00",
                "duration_minutes": 120,
            }
        ]
    }


def test_update_event_changes_matching_event() -> None:
    adapter = FakeCalendarAdapter.from_initial_state(
        {
            "calendar_events": [
                {
                    "id": "evt_marv_sync_001",
                    "title": "Meeting with Marv",
                    "start_date": "2026-05-18",
                    "start_time": "14:00",
                    "duration_minutes": 30,
                }
            ]
        }
    )

    result = adapter.update_event(
        event_id="evt_marv_sync_001",
        start_time="17:00",
    )

    events = adapter.export_state()["calendar_events"]
    assert result.success is True
    assert result.tool == "calendar.update_event"
    assert events[0]["title"] == "Meeting with Marv"
    assert events[0]["start_time"] == "17:00"
    assert events[0]["duration_minutes"] == 30


def test_update_event_returns_failure_for_missing_event() -> None:
    adapter = FakeCalendarAdapter.from_initial_state({"calendar_events": []})

    result = adapter.update_event(
        event_id="evt_missing_001",
        start_time="17:00",
    )

    assert result.success is False
    assert result.tool == "calendar.update_event"
    assert result.error == "calendar event not found: evt_missing_001"
    assert adapter.export_state() == {"calendar_events": []}


def test_update_event_rejects_invalid_duration() -> None:
    adapter = FakeCalendarAdapter.from_initial_state(
        {
            "calendar_events": [
                {
                    "id": "evt_marv_sync_001",
                    "title": "Meeting with Marv",
                    "start_date": "2026-05-18",
                    "start_time": "14:00",
                    "duration_minutes": 30,
                }
            ]
        }
    )

    with pytest.raises(ValidationError):
        adapter.update_event(
            event_id="evt_marv_sync_001",
            duration_minutes=0,
        )


def test_create_event_generates_non_colliding_id() -> None:
    adapter = FakeCalendarAdapter.from_initial_state(
        {
            "calendar_events": [
                {
                    "id": "evt_fake_calendar_002",
                    "title": "Existing fake event",
                    "start_date": "2026-05-18",
                    "start_time": "14:00",
                    "duration_minutes": 30,
                }
            ]
        }
    )

    adapter.create_event(
        title="Linear algebra revision",
        start_date="2026-05-19",
        start_time="16:00",
        duration_minutes=120,
    )

    events = adapter.export_state()["calendar_events"]
    assert events[1]["id"] == "evt_fake_calendar_003"


def test_rejects_invalid_initial_calendar_event() -> None:
    with pytest.raises(ValidationError):
        FakeCalendarAdapter.from_initial_state(
            {
                "calendar_events": [
                    {
                        "id": "evt_bad_001",
                        "title": "Bad event",
                        "start_date": "2026-05-18",
                        "start_time": "14:00",
                        "duration_minutes": 0,
                    }
                ]
            }
        )
