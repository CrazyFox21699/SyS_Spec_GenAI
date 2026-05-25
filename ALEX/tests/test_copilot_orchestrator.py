"""Tests for Copilot Context Pack and orchestrator helpers."""

from unittest.mock import patch

from src.engine.signal_constraint_parser import (
    extract_signal_constraints_from_text,
    normalize_exclusive_range_definition,
    parse_structured_constraint,
)
from src.engine.given_value_resolver import definition_to_concrete_value
from web.copilot_context_pack import build_context_pack
from web.testcase_apply import build_full_row_diffs, preview_apply_drafts
from tests.test_shutoff_decision_roles import SHUTOFF_BUNDLE


def test_parse_exclusive_range_gt_lt() -> None:
    found = extract_signal_constraints_from_text("FORCE_SHUTOFF > 1 and < 6", focus_term="")
    assert found.get("FORCE_SHUTOFF") == normalize_exclusive_range_definition("1", "6")
    structured = parse_structured_constraint(found["FORCE_SHUTOFF"])
    assert structured == {"kind": "range_exclusive", "lo": "1", "hi": "6"}


def test_exclusive_range_concrete_value() -> None:
    defn = normalize_exclusive_range_definition("1", "6")
    val = definition_to_concrete_value("FORCE_SHUTOFF", defn, path_intent="satisfy")
    assert val in ("3", "3.0", "2.5", "3.5")


def test_build_context_pack_shutoff_fixture() -> None:
    bundle = {**SHUTOFF_BUNDLE, "test_candidates": [], "ai_assists": {}}
    pack = build_context_pack(bundle, "TC2_T1_01", engineer_note="OK_SHUTOFF >= 1, < 5")
    assert pack["logic_id"] == "TC2_T1_01"
    assert pack["logic"]["control_name"] == "SHUTOFF_DECISION"
    assert "OK_SHUTOFF" in pack["engineer_input"]["parsed_constraints"]
    assert pack["coverage_gaps"]["logic_id"] == "TC2_T1_01"


def test_build_full_row_diffs_noop_detection() -> None:
    bundle = {
        "logic_blocks": [{"id": "LB1", "name": "CTRL"}],
        "test_candidates": [
            {
                "id": "TC1",
                "status": "candidate",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}]},
                "use_case_description": "Same case",
            }
        ],
        "ai_assists": {
            "candidate_overlays": {
                "TC1": {
                    "en": {
                        "use_case": "Same case",
                        "operation": "Op",
                        "expected_input": "Given: A=1",
                        "expected_output": "Then: B=1",
                    }
                }
            }
        },
    }
    drafts = [
        {
            "action": "update_existing",
            "candidate_id": "TC1",
            "use_case": "Same case",
            "operation": "Op",
            "expected_input": "Given: A=1",
            "expected_output": "Then: B=1",
        }
    ]
    preview = preview_apply_drafts(bundle, "LB1", drafts)
    assert preview["noop_count"] >= 1
    assert preview["diffs"][0]["noop"] is True


def test_generate_plan_via_m365_mock() -> None:
    from web.copilot_planner import generate_plan_via_m365

    pack = {"logic_id": "LB1", "testcases": [], "coverage_gaps": {}, "style_reference": {}}
    mock_plan = {
        "understanding_summary": "test",
        "plan_items": [{"plan_item_id": "P1", "action": "add_new", "proposed_id": "TC_NEW"}],
    }
    with patch(
        "web.copilot_planner.run_copilot_chat",
        return_value='{"understanding_summary":"test","plan_items":[{"plan_item_id":"P1","action":"add_new","proposed_id":"TC_NEW"}]}',
    ):
        out = generate_plan_via_m365({}, pack, engineer_note="note")
    assert out["ok"] is True
    assert len(out["plan"]["plan_items"]) == 1
