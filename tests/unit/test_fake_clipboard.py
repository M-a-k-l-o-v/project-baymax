import pytest
from pydantic import ValidationError

from baymax.tools.fake_clipboard import FakeClipboardAdapter


def test_read_returns_clipboard_text_without_mutating_state() -> None:
    adapter = FakeClipboardAdapter.from_initial_state(
        {"clipboard": {"text": "Finish ML assignment by Friday"}}
    )

    result = adapter.read()

    assert result.success is True
    assert result.tool == "clipboard.read"
    assert result.data == {"text": "Finish ML assignment by Friday"}
    assert adapter.export_state() == {"clipboard": {"text": "Finish ML assignment by Friday"}}


def test_write_replaces_clipboard_text() -> None:
    adapter = FakeClipboardAdapter.from_initial_state({"clipboard": {"text": "Old clipboard text"}})

    result = adapter.write(text="New clipboard text")

    assert result.success is True
    assert result.tool == "clipboard.write"
    assert adapter.export_state() == {"clipboard": {"text": "New clipboard text"}}


def test_missing_clipboard_state_defaults_to_empty_text() -> None:
    adapter = FakeClipboardAdapter.from_initial_state({})

    assert adapter.export_state() == {"clipboard": {"text": ""}}
    assert adapter.read().data == {"text": ""}


def test_rejects_invalid_initial_clipboard_state() -> None:
    with pytest.raises(ValidationError):
        FakeClipboardAdapter.from_initial_state({"clipboard": {"text": 123}})
