"""Load optional .env from ALEX root (gitignored). Does not override existing env vars."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils.config_path import ALEX_ROOT


def load_dotenv(path: Path | None = None) -> bool:
    """Parse a simple KEY=VALUE .env file into os.environ."""
    env_path = path or (ALEX_ROOT / ".env")
    if not env_path.is_file():
        return False
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value
    return True
