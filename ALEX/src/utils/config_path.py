"""Resolve config file path (ALEX_CONFIG env overrides default config.yaml)."""

from __future__ import annotations

import os
from pathlib import Path

ALEX_ROOT = Path(__file__).resolve().parents[2]


def get_config_path() -> Path:
    name = os.environ.get("ALEX_CONFIG", "config.yaml").strip() or "config.yaml"
    path = Path(name)
    return path if path.is_absolute() else ALEX_ROOT / path
