"""Registry loader tests — happy path + failure modes (ADR 0012 §2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baymax.core.exceptions import IncompleteRegistryEntry, ModelNotFound
from baymax.core.registry import list_registered_models, load_registry_entry


def _write_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    manifest_path = tmp_path / "models.json"
    manifest_path.write_text(json.dumps({"models": entries}), encoding="utf-8")
    return manifest_path


def test_load_registry_entry_returns_validated_entry(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "id": "qwen-1.5b-baymax-v1",
                "base": "qwen-1.5b",
                "adapter_path": "models/qwen-1.5b-baymax-v1/adapter",
                "trained_at": "2026-08-15T10:00:00Z",
                "config_hash": "abc123",
                "git_commit": "deadbeef",
                "mlx_compatible": True,
            }
        ],
    )
    entry = load_registry_entry("qwen-1.5b-baymax-v1", registry_path=manifest)
    assert entry.id == "qwen-1.5b-baymax-v1"
    assert entry.base == "qwen-1.5b"
    assert entry.adapter_path == "models/qwen-1.5b-baymax-v1/adapter"
    assert entry.config_hash == "abc123"
    assert entry.git_commit == "deadbeef"
    assert entry.mlx_compatible is True


def test_load_registry_entry_allows_null_optional_fields(tmp_path: Path) -> None:
    """Base OpenAI-style entry: adapter_path / trained_at / config_hash may be null."""
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "id": "gpt-4o-mini",
                "base": "gpt-4o-mini",
                "adapter_path": None,
                "trained_at": None,
                "config_hash": None,
            }
        ],
    )
    entry = load_registry_entry("gpt-4o-mini", registry_path=manifest)
    assert entry.adapter_path is None
    assert entry.trained_at is None
    assert entry.config_hash is None


def test_load_registry_entry_raises_model_not_found_when_missing(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "id": "some-other",
                "base": "b",
                "adapter_path": None,
                "trained_at": None,
                "config_hash": None,
            }
        ],
    )
    with pytest.raises(ModelNotFound) as exc_info:
        load_registry_entry("qwen-1.5b-baymax-v99", registry_path=manifest)
    assert exc_info.value.model_id == "qwen-1.5b-baymax-v99"


def test_load_registry_entry_raises_model_not_found_when_registry_absent(tmp_path: Path) -> None:
    """Missing registry file surfaces the same actionable error as missing entry."""
    with pytest.raises(ModelNotFound):
        load_registry_entry("anything", registry_path=tmp_path / "does-not-exist.json")


def test_load_registry_entry_raises_incomplete_when_required_field_missing(tmp_path: Path) -> None:
    """Missing `config_hash` is a required-field violation per ADR 0012 §2."""
    manifest = _write_manifest(
        tmp_path,
        [
            {
                "id": "broken-entry",
                "base": "qwen-1.5b",
                "adapter_path": "models/broken/adapter",
                "trained_at": "2026-08-15T10:00:00Z",
                # config_hash intentionally absent
            }
        ],
    )
    with pytest.raises(IncompleteRegistryEntry) as exc_info:
        load_registry_entry("broken-entry", registry_path=manifest)
    assert "config_hash" in exc_info.value.missing_fields


def test_list_registered_models_returns_ids(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            {"id": "a", "base": "b", "adapter_path": None, "trained_at": None, "config_hash": None},
            {"id": "b", "base": "b", "adapter_path": None, "trained_at": None, "config_hash": None},
        ],
    )
    assert set(list_registered_models(registry_path=manifest)) == {"a", "b"}


def test_list_registered_models_returns_empty_when_registry_absent(tmp_path: Path) -> None:
    assert list_registered_models(registry_path=tmp_path / "missing.json") == []


def test_shipped_registry_seed_loads_gpt_4o_mini() -> None:
    """The committed models/models.json has a working gpt-4o-mini entry."""
    entry = load_registry_entry("gpt-4o-mini")
    assert entry.id == "gpt-4o-mini"
    assert entry.mlx_compatible is False
