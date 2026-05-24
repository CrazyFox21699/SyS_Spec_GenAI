"""Formal spec structure zones (section skeleton, not business semantics)."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class LogicZone(str, Enum):
    """Canonical zones in Word/Excel logic specifications."""

    metadata = "metadata"
    overview = "overview"
    definitions = "definitions"
    control_conditions = "control_conditions"
    state_charts = "state_charts"
    constants = "constants"
    changelog = "changelog"
    unknown = "unknown"


SECTION_HEADER_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.\s+(.+?)\s*$")

_ZONE_TITLE_RULES: list[tuple[LogicZone, re.Pattern[str]]] = [
    (LogicZone.overview, re.compile(r"\boverview\b", re.I)),
    (LogicZone.definitions, re.compile(r"\b(definition|terminology|glossary)\b", re.I)),
    (LogicZone.control_conditions, re.compile(r"\bcontrol\s+conditions?\b", re.I)),
    (
        LogicZone.state_charts,
        re.compile(r"\b(state\s+chart|timing\s+chart|transition\s+diagram)\b", re.I),
    ),
    (LogicZone.constants, re.compile(r"\bconstants?\b", re.I)),
    (LogicZone.changelog, re.compile(r"\b(changelog|change\s+log|revision\s+history)\b", re.I)),
    (
        LogicZone.metadata,
        re.compile(r"\b(specification\s+number|document\s+classification|version)\b", re.I),
    ),
]


def zone_from_section_title(title: str) -> LogicZone:
    """Map a section heading or standalone title to a LogicZone."""
    text = str(title or "").strip()
    if not text:
        return LogicZone.unknown
    m = SECTION_HEADER_RE.match(text)
    body = m.group(2).strip() if m else text
    for zone, pattern in _ZONE_TITLE_RULES:
        if pattern.search(body):
            return zone
    return LogicZone.unknown


def zone_to_dict(zone: LogicZone) -> dict[str, str]:
    return {"zone": zone.value, "label": zone.name}


def build_spec_profile(
    *,
    file_name: str,
    is_logic_spec: bool,
    classifier_score: float,
    classifier_signals: list[str],
    section_zones: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate document-level spec profile (additive artifact)."""
    return {
        "file": file_name,
        "is_logic_spec": is_logic_spec,
        "classifier_score": round(classifier_score, 4),
        "classifier_signals": classifier_signals,
        "section_zones": section_zones,
    }
