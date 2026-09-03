"""Model registry loader.

Per ADR 0012 — the registry is a `models/models.json` manifest at repo root.
Each entry describes one model (base or fine-tune) that a backend may serve.

Backends read a single entry at construction time (`load_registry_entry`)
per ADR 0011 §7 (registry-driven metadata). The registry is single source
of truth for model IDENTITY (id, base, adapter_path, provenance);
benchmark scores live in `results/*.json` per METHODOLOGY §8.

Immutable model IDs (per RONIN_SYNC B3): retraining creates a new ID
(`v1 → v2 → v3`); existing entries are never rewritten.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from baymax.core.exceptions import IncompleteRegistryEntry, ModelNotFound

# Repo-root default. Callers may pass an override for tests.
_DEFAULT_REGISTRY_PATH = Path("models/models.json")

# Required per ADR 0012 §2. `adapter_path` may be null (base models with
# no adapter — e.g., an OpenAI-served model registered for uniformity).
# `trained_at` and `config_hash` may be null for base models that were
# never trained (e.g., raw HF checkpoint or a hosted OpenAI model).
_REQUIRED_FIELDS = ("id", "base", "adapter_path", "trained_at", "config_hash")


@dataclass(frozen=True)
class ModelEntry:
    """Validated registry entry — the shape backends actually consume."""

    id: str
    base: str
    adapter_path: str | None  # relative to repo root; null for base-only models
    trained_at: str | None  # ISO 8601 datetime; null for base models
    config_hash: str | None  # sha256 of training config; null for base models
    # Optional fields (§2 optional table). Kept as raw dict for extensibility;
    # backends can pull what they need via .get(...).
    extras: dict[str, Any]

    @property
    def git_commit(self) -> str | None:
        return self.extras.get("git_commit")

    @property
    def checkpoint_format(self) -> str | None:
        return self.extras.get("checkpoint_format")

    @property
    def mlx_compatible(self) -> bool:
        return bool(self.extras.get("mlx_compatible", False))

    @property
    def mlx_artifact_path(self) -> str | None:
        return self.extras.get("mlx_artifact_path")


def load_registry_entry(
    model_id: str,
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
) -> ModelEntry:
    """Look up one entry by `model_id`.

    Raises:
        ModelNotFound: no entry matches `model_id`.
        IncompleteRegistryEntry: entry exists but is missing required fields.

    Both errors are startup-fatal per ADR 0011 §B5 (validation at lifespan;
    uvicorn exits before requests are accepted).
    """
    if not registry_path.exists():
        # Treat missing registry file the same as missing entry — same
        # actionable fix ("create models/models.json with your entry").
        raise ModelNotFound(model_id=model_id, registry_path=str(registry_path))

    manifest = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = manifest.get("models", [])
    for entry in entries:
        if entry.get("id") == model_id:
            return _validate_and_build(entry, registry_path)

    raise ModelNotFound(model_id=model_id, registry_path=str(registry_path))


def list_registered_models(
    registry_path: Path = _DEFAULT_REGISTRY_PATH,
) -> list[str]:
    """Return all model IDs in the registry. Empty list if no registry file."""
    if not registry_path.exists():
        return []
    manifest = json.loads(registry_path.read_text(encoding="utf-8"))
    return [e.get("id") for e in manifest.get("models", []) if e.get("id")]


def _validate_and_build(raw: dict[str, Any], registry_path: Path) -> ModelEntry:
    """Check required fields present; build ModelEntry."""
    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        raise IncompleteRegistryEntry(model_id=raw.get("id", "<unknown>"), missing_fields=missing)

    # Extras = everything not in the required set. Kept as raw for
    # extensibility; individual backend classes pull what they need.
    extras = {k: v for k, v in raw.items() if k not in _REQUIRED_FIELDS}

    return ModelEntry(
        id=raw["id"],
        base=raw["base"],
        adapter_path=raw["adapter_path"],
        trained_at=raw["trained_at"],
        config_hash=raw["config_hash"],
        extras=extras,
    )
