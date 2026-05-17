"""Reject lock files, temp files, and other non-ingestible paths."""

from __future__ import annotations

from pathlib import Path

SKIP_PREFIXES = ("~$", ".~", "._")
SKIP_SUFFIXES = (".tmp", ".temp", ".bak", ".swp", ".ds_store")
SKIP_EXACT = {".ds_store", "thumbs.db", "desktop.ini"}


def is_ingestible_file(path: Path) -> bool:
    name = path.name
    lower = name.lower()
    if lower in SKIP_EXACT:
        return False
    if name.startswith(SKIP_PREFIXES):
        return False
    if lower.endswith(SKIP_SUFFIXES):
        return False
    if name.startswith(".") and name not in {".gitkeep"}:
        return False
    return True


def skip_reason(path: Path) -> str | None:
    if is_ingestible_file(path):
        return None
    name = path.name
    if name.startswith("~$"):
        return "Microsoft Office lock file (close the document in Word/Excel and remove this file)"
    if name.startswith("."):
        return "Hidden or system file"
    return "Unsupported temporary or lock file"
