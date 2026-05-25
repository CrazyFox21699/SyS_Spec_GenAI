"""Text helpers."""

from __future__ import annotations

import re
import unicodedata


def normalize_ws(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s or "").split())


def contains_japanese(s: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", s or ""))
