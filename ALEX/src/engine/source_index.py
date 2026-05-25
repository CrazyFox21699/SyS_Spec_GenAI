"""Build read-only source index from parsed bundle (Excel, Word, diagram, state machine)."""

from __future__ import annotations

from typing import Any


def build_source_index(bundle: dict[str, Any]) -> dict[str, Any]:
    excel_transitions: list[dict[str, Any]] = []
    for t in bundle.get("transitions") or []:
        src = t.get("source") or {}
        excel_transitions.append(
            {
                "id": t.get("id"),
                "from_state": t.get("from_state"),
                "to_state": t.get("to_state"),
                "event": t.get("event"),
                "raw_condition": t.get("raw_condition"),
                "diagram_link": t.get("diagram_link"),
                "source_file": src.get("file"),
                "sheet": src.get("sheet"),
                "row": src.get("row"),
                "kind": src.get("kind", "excel_transition"),
            }
        )

    word_sections: list[dict[str, Any]] = []
    for lb in bundle.get("logic_blocks") or []:
        src = lb.get("source") or {}
        word_sections.append(
            {
                "logic_id": lb.get("id"),
                "control_name": lb.get("name"),
                "expression": lb.get("raw_expression"),
                "file": src.get("file") or src.get("document"),
                "table_id": src.get("table_id"),
                "parse_status": lb.get("parse_status"),
            }
        )

    diagram_assets: list[dict[str, Any]] = []
    for d in bundle.get("diagrams") or []:
        diagram_assets.append(
            {
                "file": d.get("file") or d.get("path"),
                "ocr_text": (d.get("ocr_text") or d.get("text") or "")[:500],
                "kind": d.get("kind", "diagram"),
            }
        )

    sm = bundle.get("diagram_semantics") or {}
    state_machine_summary = {
        "states_count": len(bundle.get("states") or []),
        "transitions_count": len(bundle.get("transitions") or []),
        "edges_count": (sm.get("summary") or {}).get("edges_total", 0),
    }

    return {
        "excel_transitions": excel_transitions,
        "word_sections": word_sections,
        "diagram_assets": diagram_assets,
        "state_machine": state_machine_summary,
        "footnote_count": len(bundle.get("footnote_definitions") or []),
    }
