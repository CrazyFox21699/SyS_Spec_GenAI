"""Canonical logic keywords from formal PM specifications."""

from __future__ import annotations

import re

LOGIC_GATES = frozenset({"AND", "OR", "NOT"})

LIFECYCLE_KEYWORDS: dict[str, str] = {
    "get started": "start",
    "finish": "finish",
    "initial value": "initial_value",
}

EDGE_EVENT_RE = re.compile(
    r"(?P<left>[A-Za-z0-9_= ]+?)\s*(?:→|->)\s*(?P<right>[A-Za-z0-9_= ]+)",
    re.I,
)
BINARY_EDGE_RE = re.compile(
    r"\b(?P<left>OFF|ON|0|1|==0|==1)\s*(?:→|->)\s*(?P<right>OFF|ON|0|1|==0|==1)\b",
    re.I,
)

_INITIAL_VALUE_RE = re.compile(
    r"^\s*initial\s+value\s*[=:]\s*(?P<value>.+?)\s*$",
    re.I,
)
_STATE_HEADING_RE = re.compile(
    r"^\s*(?:state\s+)?(?P<state>[A-Za-z][A-Za-z0-9_ ]{0,40})\s*:?\s*$",
    re.I,
)


def normalize_lifecycle_label(text: str) -> str | None:
    low = str(text or "").strip().lower()
    for phrase, kind in LIFECYCLE_KEYWORDS.items():
        if low == phrase or low.startswith(phrase + " "):
            return kind
    return None


def is_logic_gate(token: str) -> bool:
    return str(token or "").strip().upper() in LOGIC_GATES


def parse_edge_event(text: str) -> dict[str, str] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    m = BINARY_EDGE_RE.search(raw) or EDGE_EVENT_RE.search(raw)
    if not m:
        return None
    return {
        "from_state": m.group("left").strip(),
        "to_state": m.group("right").strip(),
        "raw": raw,
    }
