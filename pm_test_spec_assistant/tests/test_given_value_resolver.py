"""Discrete guard values and engineer definition apply."""

from src.engine.concrete_test_values import (
    _format_signal_given,
    dedupe_expected_input_text,
    materialize_expected_input,
)
from src.engine.definition_apply import apply_engineer_definitions_to_candidates
from src.engine.given_value_resolver import definition_to_concrete_value, is_discrete_guard_signal
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview


def test_discrete_guard_never_gets_1_01() -> None:
    assert is_discrete_guard_signal("OK_SHUTOFF")
    line = _format_signal_given(
        {"signal": "OK_SHUTOFF", "value": "1", "operator": ">="},
        path_intent="satisfy",
    )
    assert line == "Given: OK_SHUTOFF=1"
    assert "1.01" not in line


def test_violate_path_flips_discrete_guard() -> None:
    line = _format_signal_given(
        {"signal": "OK_SHUTOFF", "value": "1", "operator": "=="},
        path_intent="violate",
    )
    assert line == "Given: OK_SHUTOFF=0"


def test_dedupe_removes_duplicate_given_signals() -> None:
    text = dedupe_expected_input_text("Given: OK_SHUTOFF=1.01\nGiven: OK_SHUTOFF=TRUE")
    assert text.count("OK_SHUTOFF") == 1
    assert "1.01" not in text
    assert "TRUE" in text or "=1" in text.replace(" ", "")


def test_engineer_definition_updates_candidates() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "control_name": "SHUTOFF_DECISION", "path_id": "path_1"},
                "operation": {
                    "given": [
                        {"signal": "OK_SHUTOFF", "value": "99", "operator": ">="},
                        {"signal": "SHUTOFF_DECISION", "value": "1", "operator": "=="},
                    ]
                },
            },
        ],
        "ai_assists": {
            "engineer_definitions": {
                "OK_SHUTOFF": {"name": "OK_SHUTOFF", "definition": "= 1", "logic_id": "LB1"},
            }
        },
    }
    n = apply_engineer_definitions_to_candidates(bundle, "LB1")
    assert n == 1
    given = bundle["test_candidates"][0]["operation"]["given"]
    by_sig = {g["signal"]: g["value"] for g in given if g.get("signal")}
    assert by_sig["OK_SHUTOFF"] == "1"
    assert "SHUTOFF_DECISION" not in by_sig
    text = materialize_expected_input(bundle["test_candidates"][0])
    assert "Given: OK_SHUTOFF=1" in text
    assert "1.01" not in text


def test_preview_uses_engineer_definition_without_duplicate_true() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "test_function": "t",
                "event": "e",
                "use_case_description": "u",
                "traceability": {"logic_block": "LB1", "control_name": "SHUTOFF_DECISION"},
                "operation": {"given": [{"signal": "OK_SHUTOFF", "value": "1", "operator": ">="}]},
                "expectation": [{"signal": "SHUTOFF_DECISION", "value": "1"}],
            }
        ],
        "ai_assists": {
            "engineer_definitions": {
                "OK_SHUTOFF": {"name": "OK_SHUTOFF", "definition": "TRUE", "logic_id": "LB1", "kind": "engineer"},
            }
        },
    }
    row = build_customer_testspec_preview(bundle)["rows"][0]
    assert row["expected_input"].count("OK_SHUTOFF") == 1
    assert "1.01" not in row["expected_input"]
    assert "OK_SHUTOFF=1" in row["expected_input"]


def test_numeric_speed_still_uses_boundary_on_violate() -> None:
    val = definition_to_concrete_value("VEH_SPD", "> 2 km/h", path_intent="violate")
    assert val == "2.01 km/h"
