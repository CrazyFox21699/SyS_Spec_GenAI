"""Tests for brief readiness gate."""

from web.brief_readiness import validate_brief_readiness
from web.m365_brief import build_copilot_brief


def _bundle_with_logic():
    return {
        "logic_blocks": [
            {
                "id": "LB1",
                "name": "CTRL",
                "raw_expression": "A AND B",
                "parse_status": "partial",
                "unresolved_refs": ["TERM_X"],
            }
        ],
        "logic_review_items": [
            {
                "logic_id": "LB1",
                "control_name": "CTRL",
                "parse_status": "partial",
                "table_rows": [{"row_no": 1, "depth": 0, "raw_condition": "A", "parser_reason": "ok"}],
                "tree_lines": ["└── A"],
            }
        ],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "path_id": "branch_1"},
                "operation": {"given": [{"signal": "A", "value": "0", "operator": "=="}]},
            }
        ],
        "issues": [
            {
                "type": "unresolved_condition",
                "severity": "error",
                "message": "missing TERM_X",
                "affected_items": ["LB1"],
            }
        ],
    }


def test_readiness_ok_with_note_and_cases():
    bundle = _bundle_with_logic()
    out = validate_brief_readiness(bundle, "LB1", "A=1 when B=0")
    assert out["ok"] is True
    assert out["test_case_count"] == 1
    assert out["blockers"] == []
    assert out["engineer_note_present"] is True


def test_readiness_blocks_no_test_cases():
    bundle = {"logic_blocks": [{"id": "LB1", "name": "C", "raw_expression": "X"}], "test_candidates": []}
    out = validate_brief_readiness(bundle, "LB1", "note")
    assert out["ok"] is False
    assert any("No test cases" in b for b in out["blockers"])


def test_readiness_blocks_empty_expression():
    bundle = {
        "logic_blocks": [{"id": "LB1", "name": "C", "raw_expression": ""}],
        "logic_review_items": [{"logic_id": "LB1", "parse_status": "failed"}],
        "test_candidates": [{"id": "TC1", "traceability": {"logic_block": "LB1"}, "operation": {}}],
    }
    out = validate_brief_readiness(bundle, "LB1", "")
    assert out["ok"] is False
    assert any("expression" in b.lower() for b in out["blockers"])


def test_build_brief_includes_enriched_sections():
    bundle = _bundle_with_logic()
    text = build_copilot_brief(bundle, "LB1", "A = 1")
    assert "Open issues" in text
    assert "Source table excerpt" in text
    assert "Condition tree" in text
    assert "path intent" in text.lower() or "path_id" in text or "branch_1" in text
    assert "Missing definitions" in text
    assert "TERM_X" in text
