"""Tests for FakeAdapterDispatcher.

Skip-marked if Ronin's fake-adapter modules aren't available locally
(i.e., PR #3 not yet merged).
"""

from __future__ import annotations

import pytest

from baymax.core.contracts import ToolCallStep

fake_modules_available = True
try:
    import baymax.tools.fake_base  # noqa: F401
    import baymax.tools.fake_calendar  # noqa: F401
    import baymax.tools.fake_clipboard  # noqa: F401
    import baymax.tools.fake_gmail  # noqa: F401
    import baymax.tools.fake_notion  # noqa: F401
except ImportError:
    fake_modules_available = False

pytestmark = pytest.mark.skipif(
    not fake_modules_available,
    reason="Ronin's fake adapter modules not yet available (PR #3 not merged).",
)


@pytest.mark.asyncio
async def test_dispatcher_routes_clipboard_read():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={"clipboard": {"text": "hello"}})
    result = await disp(ToolCallStep(tool="clipboard.read", arguments={}))
    assert result.success
    assert result.tool == "clipboard.read"
    assert result.data.get("text") == "hello"


@pytest.mark.asyncio
async def test_dispatcher_routes_clipboard_write_then_read():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    write = await disp(ToolCallStep(tool="clipboard.write", arguments={"text": "world"}))
    assert write.success
    read = await disp(ToolCallStep(tool="clipboard.read", arguments={}))
    assert read.success
    assert read.data["text"] == "world"


@pytest.mark.asyncio
async def test_dispatcher_routes_notion_create_task():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    result = await disp(ToolCallStep(tool="notion.create_task", arguments={"title": "buy milk"}))
    assert result.success
    assert "task_id" in result.data or "id" in result.data


@pytest.mark.asyncio
async def test_dispatcher_routes_calendar_create_event():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    result = await disp(
        ToolCallStep(
            tool="calendar.create_event",
            arguments={
                "title": "Meeting",
                "start_date": "2026-06-25",
                "start_time": "09:00",
                "duration_minutes": 30,
            },
        )
    )
    assert result.success
    assert "event_id" in result.data


@pytest.mark.asyncio
async def test_dispatcher_unknown_namespace_returns_failure():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    result = await disp(ToolCallStep(tool="unknown.thing", arguments={}))
    assert not result.success
    assert "no adapter" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_dispatcher_unknown_method_returns_failure():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    result = await disp(ToolCallStep(tool="clipboard.nonexistent", arguments={}))
    assert not result.success
    assert "method" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_dispatcher_bad_arguments_returns_failure():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    # clipboard.write requires text= kwarg; we pass something else
    result = await disp(ToolCallStep(tool="clipboard.write", arguments={"wrong": "x"}))
    assert not result.success


@pytest.mark.asyncio
async def test_dispatcher_export_state_after_writes():
    from baymax.core.dispatcher import FakeAdapterDispatcher

    disp = FakeAdapterDispatcher(initial_state={})
    await disp(ToolCallStep(tool="clipboard.write", arguments={"text": "exported"}))
    state = disp.export_state()
    # Each adapter contributes its own state key
    assert "clipboard" in state
    assert "notion_tasks" in state
    assert "calendar_events" in state
    assert state["clipboard"]["text"] == "exported"
