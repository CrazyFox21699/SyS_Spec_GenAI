"""Map Word document body order to canonical LogicZone sections."""

from __future__ import annotations

import re
from typing import Any, Iterator

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.models.spec_profile import LogicZone, SECTION_HEADER_RE, zone_from_section_title

_STANDALONE_ZONE_TITLES = re.compile(
    r"^(constants?|definitions?|control\s+conditions?|overview|changelog)$",
    re.I,
)


def _iter_body_blocks(document: DocxDocument) -> Iterator[tuple[str, Paragraph | Table]]:
    """Yield ('paragraph', Paragraph) or ('table', Table) in document order."""
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield "paragraph", Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield "table", Table(child, document)


def _paragraph_zone_candidate(text: str) -> LogicZone | None:
    stripped = text.strip()
    if not stripped:
        return None
    if SECTION_HEADER_RE.match(stripped):
        zone = zone_from_section_title(stripped)
        return zone if zone != LogicZone.unknown else None
    if _STANDALONE_ZONE_TITLES.match(stripped):
        return zone_from_section_title(stripped)
    return None


def build_word_section_map(document: DocxDocument) -> dict[str, Any]:
    """
    Walk body blocks; record sections and table_index -> LogicZone mapping.
    Tables before any detected section use zone=unknown (legacy flat-scan compatible).
    """
    sections: list[dict[str, Any]] = []
    table_zones: dict[int, LogicZone] = {}
    current_zone = LogicZone.unknown
    table_index = 0

    for kind, block in _iter_body_blocks(document):
        if kind == "paragraph":
            text = block.text.strip()
            candidate = _paragraph_zone_candidate(text)
            if candidate is not None:
                current_zone = candidate
                sections.append(
                    {
                        "title": text,
                        "zone": current_zone.value,
                        "table_index_before": table_index,
                    }
                )
            continue

        table_zones[table_index] = current_zone
        table_index += 1

    return {
        "sections": sections,
        "table_zones": {str(k): v.value for k, v in table_zones.items()},
    }


def zone_for_table(table_index: int, section_map: dict[str, Any]) -> LogicZone:
    raw = (section_map.get("table_zones") or {}).get(str(table_index), LogicZone.unknown.value)
    try:
        return LogicZone(str(raw))
    except ValueError:
        return LogicZone.unknown


def annotate_source_with_zone(source: dict[str, Any], zone: LogicZone) -> dict[str, Any]:
    """Return a copy of source with optional section_zone (additive)."""
    out = dict(source)
    out["section_zone"] = zone.value
    return out
