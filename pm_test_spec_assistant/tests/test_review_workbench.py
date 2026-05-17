from __future__ import annotations

from src.engine.logic_review_builder import build_logic_review_items
from web.review_workbench import build_ai_queue, build_capability_summary, build_definition_inbox


def test_definition_inbox_explains_normalized_match() -> None:
    logic_blocks = [
        {
            "id": "LOGIC_100",
            "name": "POWER_DECISION",
            "block_type": "two_column_control",
            "raw_expression": "POWER=OFF",
            "tree": {"type": "condition"},
            "unresolved_refs": ["POWER=OFF"],
            "parse_status": "ok",
            "source": {"file": "spec.docx", "table": "table_9"},
        }
    ]
    items = build_logic_review_items(
        logic_blocks,
        [],
        [
            {
                "id": "TC_100",
                "test_function": "Power decision",
                "event": "POWER_DECISION",
                "traceability": {"source_evidence": ["spec.docx / table_9"], "logic": "LOGIC_100"},
                "review_status": "pending",
                "review_required": True,
            }
        ],
        [],
        [],
        [],
        [],
        [],
        [
            {
                "name": "POWER_OFF",
                "definition": "Power state equals OFF.",
                "logic_id": "LOGIC_100",
                "source": {"file": "define.xlsx", "sheet": "Definitions", "row": 3},
            }
        ],
    )
    bundle = {
        "logic_review_items": items,
        "condition_definitions": [],
        "alias_map": [],
        "footnote_definitions": [],
        "test_candidates": [
            {
                "id": "TC_100",
                "test_function": "Power decision",
                "event": "POWER_DECISION",
                "traceability": {"source_evidence": ["spec.docx / table_9"], "logic": "LOGIC_100"},
                "review_status": "pending",
                "review_required": True,
            }
        ],
        "ai_assists": {
            "supplemental_definitions": {
                "LOGIC_100": [
                    {
                        "name": "POWER_OFF",
                        "definition": "Power state equals OFF.",
                        "logic_id": "LOGIC_100",
                        "source": {"file": "define.xlsx", "sheet": "Definitions", "row": 3},
                    }
                ]
            }
        },
    }

    inbox = build_definition_inbox(bundle, "LOGIC_100")

    assert inbox["terms"][0]["resolution"] == "added_context_found"
    assert inbox["terms"][0]["reason_code"] == "normalized_match"
    assert inbox["terms"][0]["definitions"][0]["match_mode"] == "normalized"


def test_ai_queue_only_runs_ready_groups() -> None:
    logic_blocks = [
        {
            "id": "LOGIC_READY",
            "name": "READY_CTRL",
            "block_type": "two_column_control",
            "raw_expression": "COND_OK",
            "tree": {"type": "condition"},
            "unresolved_refs": [],
            "parse_status": "ok",
            "source": {"file": "spec.docx", "table": "table_ready"},
        },
        {
            "id": "LOGIC_BLOCKED",
            "name": "BLOCKED_CTRL",
            "block_type": "two_column_control",
            "raw_expression": "COND_MISSING",
            "tree": {"type": "condition"},
            "unresolved_refs": ["COND_MISSING"],
            "parse_status": "ok",
            "source": {"file": "spec.docx", "table": "table_blocked"},
        },
    ]
    items = build_logic_review_items(
        logic_blocks,
        [],
        [
            {
                "id": "TC_READY",
                "test_function": "Ready function",
                "event": "READY_CTRL",
                "traceability": {"source_evidence": ["spec.docx / table_ready"], "logic": "LOGIC_READY"},
                "review_status": "pending",
                "review_required": True,
            },
            {
                "id": "TC_BLOCKED",
                "test_function": "Blocked function",
                "event": "BLOCKED_CTRL",
                "traceability": {"source_evidence": ["spec.docx / table_blocked"], "logic": "LOGIC_BLOCKED"},
                "review_status": "pending",
                "review_required": True,
            },
        ],
        [],
        [{"name": "COND_OK", "definition": "condition ok", "source": {"file": "spec.docx"}}],
        [],
        [],
    )
    bundle = {
        "logic_review_items": items,
        "test_candidates": [
            {
                "id": "TC_READY",
                "test_function": "Ready function",
                "event": "READY_CTRL",
                "traceability": {"source_evidence": ["spec.docx / table_ready"], "logic": "LOGIC_READY"},
                "review_status": "pending",
                "review_required": True,
            },
            {
                "id": "TC_BLOCKED",
                "test_function": "Blocked function",
                "event": "BLOCKED_CTRL",
                "traceability": {"source_evidence": ["spec.docx / table_blocked"], "logic": "LOGIC_BLOCKED"},
                "review_status": "pending",
                "review_required": True,
            },
        ],
        "ai_assists": {},
    }

    queue = build_ai_queue(bundle)

    assert queue["summary"]["ready_for_ai"] == 1
    assert queue["summary"]["blocked_missing_definition"] == 1
    assert queue["run_logic_ids"] == ["LOGIC_READY"]


def test_definition_inbox_marks_engineer_note_as_resolved_context() -> None:
    logic_blocks = [
        {
            "id": "LOGIC_VEH",
            "name": "NOK_SHUTOFF",
            "block_type": "two_column_control",
            "raw_expression": "VEH_SPD > 0",
            "tree": {"type": "condition"},
            "unresolved_refs": ["VEH_SPD"],
            "parse_status": "ok",
            "source": {"file": "spec.xlsx", "table": "table_1"},
        }
    ]
    items = build_logic_review_items(
        logic_blocks,
        [],
        [
            {
                "id": "TC_VEH",
                "test_function": "Vehicle speed review",
                "event": "NOK_SHUTOFF",
                "traceability": {"source_evidence": ["spec.xlsx / table_1"], "logic": "LOGIC_VEH"},
                "review_status": "pending",
                "review_required": True,
            }
        ],
        [],
        [],
        [],
        [],
        [{"name": "VEH_SPD", "definition": "Vehicle speed", "logic_id": "LOGIC_VEH", "source": {"file": "engineer_clarification"}}],
        [],
    )
    bundle = {
        "logic_review_items": items,
        "condition_definitions": [],
        "alias_map": [],
        "footnote_definitions": [],
        "test_candidates": [
            {
                "id": "TC_VEH",
                "test_function": "Vehicle speed review",
                "event": "NOK_SHUTOFF",
                "traceability": {"source_evidence": ["spec.xlsx / table_1"], "logic": "LOGIC_VEH"},
                "review_status": "pending",
                "review_required": True,
            }
        ],
        "ai_assists": {
            "engineer_definitions": {
                "VEH_SPD": {"name": "VEH_SPD", "definition": "Vehicle speed", "logic_id": "LOGIC_VEH"}
            }
        },
    }

    inbox = build_definition_inbox(bundle, "LOGIC_VEH")

    assert inbox["terms"][0]["resolution"] == "added_context_found"
    assert inbox["terms"][0]["reason_code"] == "engineer_note_only"


def test_capability_summary_reports_current_limits() -> None:
    bundle = {
        "logic_review_items": [
            {"logic_id": "L1", "parse_status": "ok"},
            {"logic_id": "L2", "parse_status": "partial"},
            {"logic_id": "L3", "parse_status": "failed"},
        ],
        "transitions": [
            {"derivation": "table_rule"},
            {"derivation": "diagram_text"},
            {"derivation": "diagram_image_metadata"},
        ],
        "footnote_definitions": [{"condition_name": "COND_A", "ref": "*1", "definition": "note"}],
        "condition_definitions": [
            {"name": "COND_A", "definition": "MODE_STS=1"},
            {"name": "COND_B", "definition": "Power is TRUE"},
        ],
        "test_candidates": [
            {
                "id": "TC_1",
                "review_status": "pending",
                "review_required": True,
            },
            {
                "id": "TC_2",
                "review_status": "ready",
                "review_required": False,
            },
        ],
        "ai_assists": {
            "candidate_overlays": {
                "TC_2": {"provider": "copilot_cli", "review_required": False, "en": {}}
            }
        },
    }

    summary = build_capability_summary(bundle)

    assert summary["logic"]["groups_ok"] == 1
    assert summary["logic"]["groups_partial"] == 1
    assert summary["logic"]["groups_failed"] == 1
    assert summary["transitions"]["diagram_shape_semantic_parse"] is False
    assert summary["definitions"]["conditions_with_value_text"] == 2
    assert summary["workbook"]["rows_with_ai_overlay"] == 1
