"""Simple persistent config for Baymax.

Stores a small JSON file under ~/.baymax/config.json so users don't need
to repeatedly export environment variables each session.

API:
- `get(key, default=None)`
- `set(key, value)`
- `load()` / `save()` (internal)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def _config_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".baymax"


def _config_file() -> Path:
    return _config_dir() / "config.json"


def load() -> Dict[str, Any]:
    p = _config_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(cfg: Dict[str, Any]) -> None:
    d = _config_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = _config_file()
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get(key: str, default: Any = None) -> Any:
    cfg = load()
    return cfg.get(key, default)


def set(key: str, value: Any) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)
