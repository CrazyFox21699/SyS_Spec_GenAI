from __future__ import annotations

from src.engine.understanding_gate import build_resolved_logic_blocks
from src.engine.understanding_loop import collect_known_terms_for_block, rebuild_understanding


def test_engineer_definition_clears_unresolved_and_rebuilds_loop() -> None:
    lb = {
        "id": "LB1",
        "name": "SYS_SHUTOFF",
        "block_type": "two_column_control",
        "parse_status": "partial",
        "raw_expression": "REQ_MAIN_OK",
        "tree": {
            "type": "condition",
            "name": "REQ_MAIN_OK",
            "raw_text": "REQ_MAIN_OK",
        },
        "unresolved_refs": ["REQ_MAIN_OK", "VEHICLE_SAFE"],
    }
    bundle = {
        "logic_blocks": [lb],
        "two_column_tables": [],
        "test_candidates": [],
        "issues": [],
        "condition_definitions": [],
        "alias_map": [],
        "footnote_definitions": [],
        "classified_files": [],
        "unresolved_items": [],
        "ingest_skipped": [],
        "ai_assists": {
            "engineer_definitions": {
                "REQ_MAIN_OK": {
                    "definition": "= 1 when main request valid",
                    "logic_id": "LB1",
                }
            }
        },
    }
    result = rebuild_understanding(bundle, trigger="test")
    assert result["ok"] is True
    assert "REQ_MAIN_OK" not in (bundle["logic_blocks"][0].get("unresolved_refs") or [])
    assert "VEHICLE_SAFE" in (bundle["logic_blocks"][0].get("unresolved_refs") or [])
    assert result["unresolved_cleared"] >= 1
    assert bundle.get("understanding_loop", {}).get("last_trigger") == "test"
    assert bundle.get("resolved_logic_blocks")
    assert bundle.get("logic_review_items")
    assert bundle.get("spec_understanding")


def test_build_resolved_logic_blocks_honors_per_block_known() -> None:
    lb_a = {
        "id": "A",
        "name": "CTRL_A",
        "parse_status": "ok",
        "tree": {"type": "condition", "name": "SIG_A", "raw_text": "SIG_A"},
        "unresolved_refs": [],
    }
    lb_b = {
        "id": "B",
        "name": "CTRL_B",
        "parse_status": "ok",
        "tree": {"type": "condition", "name": "SIG_B", "raw_text": "SIG_B"},
        "unresolved_refs": ["SIG_B"],
    }
    known = {
        "A": collect_known_terms_for_block(
            {
                "ai_assists": {
                    "engineer_definitions": {
                        "SIG_A": {"definition": "active when valid", "logic_id": "A"},
                    }
                },
                "condition_definitions": [],
            },
            "A",
            "CTRL_A",
        )
    }
    resolved = build_resolved_logic_blocks([lb_a, lb_b], known_by_block_id=known)
    by_id = {r["id"]: r for r in resolved}
    assert by_id["A"]["gate_status"] == "ready"
    assert by_id["B"]["gate_status"] == "needs_engineer"
