"""Signal registry schema helpers."""

from __future__ import annotations

from typing import Any

SIGNAL_FIELDS = (
    "name",
    "description",
    "sender",
    "direction",
    "values",
    "initial_value",
    "fail_safe_value",
    "fail_safe_domain",
    "definition",
    "source",
    "confidence",
    "review_required",
)


def normalize_signal_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: row.get(k) for k in SIGNAL_FIELDS if k in row or k in ("name", "description")}
    out.setdefault("values", [])
    out.setdefault("review_required", True)
    return out
