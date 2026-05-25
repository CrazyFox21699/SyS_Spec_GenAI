from __future__ import annotations

from src.engine.path_tc_matrix import build_path_tc_matrix, enrich_candidate_coverage
from src.engine.selective_tc_regen import build_path_regen_proposals


def _sample_bundle() -> dict:
    tree = {
        "type": "OR",
        "children": [
            {"type": "boolean_predicate", "signal": "SIG_A", "raw_text": "SIG_A"},
            {"type": "boolean_predicate", "signal": "SIG_B", "raw_text": "SIG_B"},
        ],
    }
    return {
        "logic_blocks": [
            {
                "id": "LB1",
                "name": "CTRL",
                "parse_status": "ok",
                "raw_expression": "SIG_A OR SIG_B",
                "tree": tree,
                "gate_status": "ready",
            }
        ],
        "resolved_logic_blocks": [
            {
                "id": "LB1",
                "name": "CTRL",
                "parse_status": "ok",
                "raw_expression": "SIG_A OR SIG_B",
                "tree": tree,
                "gate_status": "ready",
            }
        ],
        "test_candidates": [
            {
                "id": "TC_PM_001",
                "traceability": {"logic_block": "LB1", "logic_path": "path_1"},
                "operation": {"given": [{"signal": "SIG_A", "value": "1"}]},
            }
        ],
    }


def test_build_path_tc_matrix_lists_or_branches() -> None:
    matrix = build_path_tc_matrix(_sample_bundle(), "LB1")
    assert matrix["ok"] is True
    assert matrix["summary"]["path_count"] >= 2
    covered = [p for p in matrix["paths"] if p["coverage_status"] == "full"]
    assert len(covered) >= 1


def test_enrich_candidate_coverage_writes_coverage_block() -> None:
    bundle = _sample_bundle()
    build_path_tc_matrix(bundle, "LB1")
    updated = enrich_candidate_coverage(bundle, "LB1")
    assert updated >= 1
    cand = bundle["test_candidates"][0]
    assert cand.get("coverage", {}).get("path_id")
    assert cand.get("coverage", {}).get("logic_id") == "LB1"


def test_path_regen_proposes_missing_paths() -> None:
    bundle = _sample_bundle()
    proposal = build_path_regen_proposals(bundle, "LB1")
    assert proposal["ok"] is True
    assert proposal["proposed_count"] >= 1
    assert proposal["reconciliation"]["summary"]["add_new"] >= 1
