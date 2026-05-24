"""Constraint compiler and structured overlay."""

from src.engine.constraint_compiler import compile_constraints_to_patches
from src.engine.coverage_intent import path_coverage_intent
from src.engine.structured_overlay import accepted_constraints, get_overlay, normalize_constraint, set_overlay
from web.structured_knowledge import compile_accepted_constraints


def test_path_coverage_intent_mcdc_neg() -> None:
    cand = {"traceability": {"path_id": "path_1_mcdc_neg", "logic_block": "LB1"}}
    assert path_coverage_intent(cand) == "violate"
    cand2 = {"traceability": {"path_id": "path_1", "logic_block": "LB1"}}
    assert path_coverage_intent(cand2) == "satisfy"


def test_compile_range_assigns_satisfy_and_violate_values() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "path_id": "path_1"},
                "operation": {"given": []},
            },
            {
                "id": "TC2",
                "traceability": {"logic_block": "LB1", "path_id": "path_1_mcdc_neg"},
                "operation": {"given": []},
            },
        ],
    }
    overlay = {
        "constraints": [
            {
                "id": "C1",
                "signal": "VEH_SPD",
                "kind": "range_inclusive",
                "min": 1,
                "max": 5,
                "review_status": "accepted",
            }
        ]
    }
    patches = compile_constraints_to_patches(bundle, "LB1", overlay)
    by_id = {p["candidate_id"]: p for p in patches}
    assert len(patches) == 2
    sat = {g["signal"]: g["value"] for g in by_id["TC1"]["given"]}
    viol = {g["signal"]: g["value"] for g in by_id["TC2"]["given"]}
    assert sat["VEH_SPD"] in ("3", "1", "5", "2", "4")
    assert viol["VEH_SPD"] in ("0", "6")


def test_compile_accepted_constraints_applies_to_bundle() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "path_id": "path_1"},
                "operation": {"given": [{"signal": "VEH_SPD", "value": "99", "operator": "=="}]},
            },
        ],
    }
    set_overlay(
        bundle,
        "LB1",
        {
            "constraints": [
                normalize_constraint(
                    {
                        "signal": "VEH_SPD",
                        "kind": "range_inclusive",
                        "min": 1,
                        "max": 5,
                        "review_status": "accepted",
                    }
                )
            ]
        },
    )
    out = compile_accepted_constraints(bundle, "LB1", {"assist": {"validation_retries": 0}})
    assert out["ok"] is True
    assert out["provider"] == "constraint_compiler"
    assert out["definitions_updated"] == 1
    given = bundle["test_candidates"][0]["operation"]["given"]
    assert given[0]["signal"] == "VEH_SPD"
    assert given[0]["value"] in ("3", "1", "5", "2", "4")
    defs = bundle["ai_assists"]["engineer_definitions"]
    assert defs["VEH_SPD"]["definition"] == "range inclusive 1–5"


def test_compile_auto_accepts_draft_constraints() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "path_id": "path_1"},
                "operation": {"given": []},
            },
        ],
    }
    set_overlay(
        bundle,
        "LB1",
        {
            "constraints": [
                normalize_constraint(
                    {
                        "signal": "OK_SHUTOFF",
                        "kind": "range_inclusive",
                        "min": 1,
                        "max": 5,
                        "review_status": "draft",
                    }
                )
            ]
        },
    )
    out = compile_accepted_constraints(bundle, "LB1", {"assist": {"validation_retries": 0}})
    assert out["ok"] is True
    assert out["auto_accepted"] == 1
    assert out["definitions_updated"] == 1
    assert bundle["ai_assists"]["engineer_definitions"]["OK_SHUTOFF"]["definition"] == "range inclusive 1–5"
