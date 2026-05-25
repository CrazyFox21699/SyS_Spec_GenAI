"""Classify Control column cells in two-column logic tables."""

from __future__ import annotations

import re
from typing import Any

from src.engine.logic_keywords import normalize_lifecycle_label

_TRANSITION_OUTCOME_RE = re.compile(
    r"(?P<from>.+?)\s*(?:→|->)\s*(?P<to>.+)",
    re.I,
)


def classify_control_cell(text: str, *, as_meta: bool = False) -> str | dict[str, Any]:
    """
    Returns kind string, or metadata dict when as_meta=True.
    Kinds: logic_control | transition_outcome | lifecycle
    """
    raw = str(text or "").strip()
    if not raw:
        return {} if as_meta else "logic_control"

    norm = normalize_lifecycle_label(raw)
    if norm is not None:
        return {"kind": "lifecycle", "label": raw, "lifecycle_kind": norm} if as_meta else "lifecycle"

    m = _TRANSITION_OUTCOME_RE.search(raw)
    if m:
        meta = {
            "kind": "transition_outcome",
            "outcome_label": raw,
            "from_state": m.group("from").strip(),
            "to_state": m.group("to").strip(),
        }
        return meta if as_meta else "transition_outcome"

    return {"kind": "logic_control", "label": raw} if as_meta else "logic_control"
