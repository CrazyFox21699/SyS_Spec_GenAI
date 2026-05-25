"""Classify diagram OCR / label text into trigger vs judgment."""

from __future__ import annotations

import re
from typing import Any

_TRIGGER_RE = re.compile(r"trigger|get\s+started|transition\s+trigger", re.I)
_JUDGMENT_RE = re.compile(r"judgment|judgement|finish|evaluate", re.I)


def classify_diagram_edge_label(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {"role": "unknown", "raw": raw}
    if _TRIGGER_RE.search(raw):
        return {"role": "trigger", "raw": raw, "label": raw}
    if _JUDGMENT_RE.search(raw):
        return {"role": "judgment", "raw": raw, "label": raw}
    return {"role": "label", "raw": raw, "label": raw}


def enrich_transition_with_edge_role(transition: dict[str, Any]) -> dict[str, Any]:
    out = dict(transition)
    for key in ("event", "raw_condition"):
        val = str(out.get(key) or "")
        if not val:
            continue
        role = classify_diagram_edge_label(val)
        if role.get("role") in ("trigger", "judgment"):
            out["edge_role"] = role["role"]
            out["edge_label"] = role.get("label", val)
            break
    return out
