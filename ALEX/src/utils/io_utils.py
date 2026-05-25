"""Filesystem helpers."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup_output_files(output_dir: Path, filenames: list[str]) -> Path | None:
    """If any target exists, copy those files into output_dir/_backups/<timestamp>/."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    to_backup = [output_dir / f for f in filenames if (output_dir / f).exists()]
    if not to_backup:
        return None
    dest_root = output_dir / "_backups" / ts
    dest_root.mkdir(parents=True, exist_ok=True)
    for p in to_backup:
        shutil.copy2(p, dest_root / p.name)
    return dest_root
