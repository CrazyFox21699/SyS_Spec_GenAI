from __future__ import annotations

from openpyxl import Workbook

from src.engine.logic_review_builder import build_logic_review_items
from src.parsers.excel_parser import extract_excel_workbook


def test_extract_excel_workbook_reads_condition_definition_sheet(tmp_path) -> None:
    path = tmp_path / "Condition_Define.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Definitions"
    ws.append(["Condition", "Definition"])
    ws.append(["OK_SHUTOFF", "CND_REQ_GROUP and CND_SAFE_GROUP are true"])
    wb.save(path)

    parsed = extract_excel_workbook(path, [])

    assert parsed["condition_definitions"] == [
        {
            "name": "OK_SHUTOFF",
            "definition": "CND_REQ_GROUP and CND_SAFE_GROUP are true",
            "source": {"file": "Condition_Define.xlsx", "sheet": "Definitions", "row": 2},
        }
    ]


def test_logic_review_marks_added_definition_as_resolved() -> None:
    logic_blocks = [
        {
            "id": "LOGIC_001",
            "name": "SHUTOFF_DECISION",
            "block_type": "two_column_control",
            "raw_expression": "OK_SHUTOFF OR FORCE_SHUTOFF",
            "tree": {"type": "OR", "children": []},
            "unresolved_refs": ["OK_SHUTOFF"],
            "parse_status": "ok",
            "source": {"file": "spec.docx", "table": "table_5"},
        }
    ]
    issues = [
        {
            "type": "unresolved_condition",
            "severity": "error",
            "message": "Referenced condition `OK_SHUTOFF` has no definition in spec tables",
            "affected_items": ["LOGIC_001", "OK_SHUTOFF"],
        }
    ]
    supplemental_defs = [
        {
            "name": "OK_SHUTOFF",
            "definition": "CND_REQ_GROUP and CND_SAFE_GROUP are true",
            "logic_id": "LOGIC_001",
            "source": {"file": "Condition_Define.xlsx", "table": "logic_attachment:LOGIC_001", "row": 2},
        }
    ]

    items = build_logic_review_items(
        logic_blocks,
        [],
        [],
        issues,
        [],
        [],
        [],
        [],
        supplemental_defs,
    )

    assert len(items) == 1
    item = items[0]
    assert item["unresolved_refs"] == []
    assert item["review_resolved_terms"] == ["OK_SHUTOFF"]
    assert item["trace_rows"][0]["status"] == "resolved"
    assert item["issues"][0]["display_severity"] == "ok"
    assert "attached define file" in item["issues"][0]["resolution_note"]


def test_logic_review_matches_definition_after_name_normalization() -> None:
    logic_blocks = [
        {
            "id": "LOGIC_002",
            "name": "SHUTOFF_DECISION",
            "block_type": "two_column_control",
            "raw_expression": "POWER=OFF",
            "tree": {"type": "condition"},
            "unresolved_refs": ["POWER=OFF"],
            "parse_status": "ok",
            "source": {"file": "spec.docx", "table": "table_8"},
        }
    ]
    issues = [
        {
            "type": "unresolved_condition",
            "severity": "error",
            "message": "Referenced condition `POWER=OFF` has no definition in spec tables",
            "affected_items": ["LOGIC_002", "POWER=OFF"],
        }
    ]
    supplemental_defs = [
        {
            "name": "POWER_OFF",
            "definition": "Power state equals OFF.",
            "logic_id": "LOGIC_002",
            "source": {"file": "define.xlsx", "table": "logic_attachment:LOGIC_002", "row": 3},
        }
    ]

    items = build_logic_review_items(
        logic_blocks,
        [],
        [],
        issues,
        [],
        [],
        [],
        [],
        supplemental_defs,
    )

    item = items[0]
    assert item["unresolved_refs"] == []
    assert item["review_resolved_terms"] == ["POWER=OFF"]
    assert item["trace_rows"][0]["status"] == "resolved"


def test_logic_review_carries_visual_source_snapshot() -> None:
    logic_blocks = [
        {
            "id": "LOGIC_VIS",
            "name": "OK_SHUTOFF",
            "block_type": "two_column_control",
            "raw_expression": "CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1",
            "tree": {"type": "AND", "children": []},
            "parse_status": "ok",
            "source": {"file": "spec.docx", "table": "table_1", "control": "OK_SHUTOFF"},
            "visual_source": {
                "kind": "logic_table",
                "title": "OK_SHUTOFF",
                "source": {"file": "spec.docx", "table": "table_1"},
                "rows": [
                    {"row_no": 1, "cells": ["OK_SHUTOFF", "AND", "CND_REQ_GROUP = 1"]},
                    {"row_no": 2, "cells": ["OK_SHUTOFF", "AND", "CND_SAFE_GROUP = 1"]},
                ],
            },
        }
    ]

    items = build_logic_review_items(logic_blocks, [], [], [], [], [], [], [], [])

    assert items[0]["visual_source"]["title"] == "OK_SHUTOFF"
    assert items[0]["visual_source"]["rows"][0]["cells"][2] == "CND_REQ_GROUP = 1"
