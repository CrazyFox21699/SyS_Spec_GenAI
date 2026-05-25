from __future__ import annotations

from src.engine.concrete_test_values import materialize_expected_input, materialize_expected_output
from src.engine.footnote_conditional import given_lines_for_footnote_rule, parse_conditional_footnote
from src.engine.logic_compliance import check_logic_compliance
from src.engine.term_role_classifier import build_term_role_index, classify_term
from src.engine.test_candidate_generator import generate_candidates_from_logic_blocks
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

SHUTOFF_TREE = {
    "type": "OR",
    "children": [
        {
            "type": "AND",
            "children": [
                {"type": "condition", "name": "OK_SHUTOFF", "footnotes": []},
                {
                    "type": "NOT",
                    "children": [
                        {"type": "condition", "name": "NOK_SHUTOFF", "footnotes": ["(*1)"]},
                    ],
                },
            ],
        },
        {
            "type": "AND",
            "children": [
                {"type": "condition", "name": "FORCE_SHUTOFF", "footnotes": []},
                {"type": "condition", "name": "CND_FORCE_ALLOWED", "footnotes": []},
            ],
        },
    ],
}

SHUTOFF_BUNDLE = {
    "features_validator": True,
    "logic_blocks": [
        {
            "id": "TC2_T1_01",
            "name": "SHUTOFF_DECISION",
            "block_type": "two_column_control",
            "raw_expression": "((OK_SHUTOFF AND NOT NOK_SHUTOFF) OR (FORCE_SHUTOFF AND CND_FORCE_ALLOWED))",
            "tree": SHUTOFF_TREE,
            "parse_status": "ok",
            "can_generate_candidates": True,
            "source": {"file": "spec.docx", "table_id": "T1_01"},
        }
    ],
    "footnote_definitions": [
        {
            "ref": "(*1)",
            "definition": "Lost = 2026 when OK_SHUTOFF = 1. Otherwise, lost = 1999",
            "condition_name": "NOK_SHUTOFF",
        }
    ],
    "condition_definitions": [
        {"name": "FORCE_SHUTOFF", "definition": "value == 150"},
        {"name": "CND_FORCE_ALLOWED", "definition": "allowed == 0"},
    ],
    "transitions": [],
    "states": [],
}


def test_term_roles_shutoff_decision_is_output() -> None:
    roles = build_term_role_index(SHUTOFF_BUNDLE)
    assert roles["SHUTOFF_DECISION"]["role"] == "output_assertion"
    assert classify_term("OK_SHUTOFF") == "guard_input"
    assert classify_term("Lost", definition="Lost = 2026 when OK_SHUTOFF = 1") == "system_state"


def test_footnote_conditional_parse() -> None:
    rule = parse_conditional_footnote("Lost = 2026 when OK_SHUTOFF = 1. Otherwise, lost = 1999")
    assert rule is not None
    assert rule["variable"].lower() == "lost"
    assert rule["when_true"]["condition_signal"] == "OK_SHUTOFF"
    lines = given_lines_for_footnote_rule(rule, branch="when")
    assert any("OK_SHUTOFF=1" in ln for ln in lines)
    assert any("Lost=2026" in ln or "lost=2026" in ln.lower() for ln in lines)


def test_force_path_given_values() -> None:
    tree = SHUTOFF_TREE["children"][1]
    from src.engine.test_candidate_generator import _definition_map, _given_from_tree

    def_map = _definition_map(SHUTOFF_BUNDLE["condition_definitions"])
    given = _given_from_tree(
        tree, "", control_name="SHUTOFF_DECISION", definition_by_name=def_map
    )
    by_sig = {g["signal"]: g["value"] for g in given if g.get("signal")}
    assert by_sig.get("FORCE_SHUTOFF") == "150"
    assert by_sig.get("CND_FORCE_ALLOWED") == "0"


def test_logic_block_generates_or_branches() -> None:
    cands, _ = generate_candidates_from_logic_blocks(
        SHUTOFF_BUNDLE["logic_blocks"],
        footnote_definitions=SHUTOFF_BUNDLE["footnote_definitions"],
        condition_definitions=SHUTOFF_BUNDLE["condition_definitions"],
    )
    events = {c["event"] for c in cands}
    assert "evaluate_SHUTOFF_DECISION_ok_path" in events
    assert "evaluate_SHUTOFF_DECISION_force_path" in events


def test_preview_puts_shutoff_in_then_not_given() -> None:
    bundle = dict(SHUTOFF_BUNDLE)
    cands, _ = generate_candidates_from_logic_blocks(
        bundle["logic_blocks"],
        footnote_definitions=bundle["footnote_definitions"],
        condition_definitions=bundle["condition_definitions"],
    )
    bundle["test_candidates"] = cands[:1]
    bundle["term_roles"] = build_term_role_index(bundle)
    preview = build_customer_testspec_preview(bundle, validate_io=True)
    row = preview["rows"][0]
    assert "SHUTOFF_DECISION" in row["expected_output"]
    assert "Given: SHUTOFF_DECISION" not in row["expected_input"]
    logic = check_logic_compliance(cands[0], bundle, expected_input=row["expected_input"])
    assert "SHUTOFF_DECISION" not in (logic.get("misplaced_in_given") or [])


def test_materialize_logic_block_skips_system_state_in_then() -> None:
    cand = {
        "source": "two_column_logic_block",
        "traceability": {"logic_block": "TC2_T1_01", "control_name": "SHUTOFF_DECISION"},
        "precondition": [],
        "operation": {
            "given": [
                {"signal": "OK_SHUTOFF", "value": "1"},
                {"signal": "FORCE_SHUTOFF", "value": "150"},
            ],
            "when": [],
        },
        "expectation": [{"signal": "SHUTOFF_DECISION", "value": "1"}],
    }
    inp = materialize_expected_input(cand)
    out = materialize_expected_output(cand)
    assert "Given: OK_SHUTOFF=1" in inp
    assert "Then: SHUTOFF_DECISION=1" in out
    assert "System state" not in out
