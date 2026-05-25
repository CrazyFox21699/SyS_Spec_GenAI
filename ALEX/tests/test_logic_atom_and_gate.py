from __future__ import annotations

from src.engine.footnote_resolver import build_footnote_registry
from src.engine.logic_atom import enrich_tree_with_atoms, parse_token_to_atom
from src.engine.mcdc_planner import plan_test_paths
from src.engine.understanding_gate import build_resolved_logic_blocks, evaluate_logic_block_gate

SHUTOFF_TREE = {
    "type": "OR",
    "children": [
        {
            "type": "AND",
            "children": [
                {"type": "condition", "name": "OK_SHUTOFF = 1", "footnotes": []},
                {
                    "type": "NOT",
                    "children": [
                        {"type": "condition", "name": "NOK_SHUTOFF (*1)", "footnotes": ["1"]},
                    ],
                },
            ],
        },
        {
            "type": "AND",
            "children": [
                {"type": "condition", "name": "FORCE_SHUTOFF = 150", "footnotes": []},
                {"type": "condition", "name": "CND_FORCE_ALLOWED = 0", "footnotes": []},
            ],
        },
    ],
}


def test_parse_token_extracts_comparator_not_hardcoded() -> None:
    atom = parse_token_to_atom("FORCE_SHUTOFF = 150")
    assert atom["signal"] == "FORCE_SHUTOFF"
    assert atom["value"] == "150"
    atom2 = parse_token_to_atom("CND_FORCE_ALLOWED = 0")
    assert atom2["value"] == "0"


def test_footnote_registry_and_gate_ready() -> None:
    footnotes = [
        {
            "ref": "(*1)",
            "definition": "Lost = 2026 when OK_SHUTOFF = 1. Otherwise, lost = 1999",
            "condition_name": "NOK_SHUTOFF",
        }
    ]
    lb = {
        "id": "T1",
        "name": "SHUTOFF_DECISION",
        "tree": SHUTOFF_TREE,
        "parse_status": "ok",
        "raw_expression": "((OK AND NOT NOK) OR (FORCE AND CND))",
    }
    resolved = build_resolved_logic_blocks([lb], footnote_definitions=footnotes)
    assert len(resolved) == 1
    assert resolved[0]["gate_status"] in ("ready", "needs_llm")
    assert len(resolved[0]["footnote_variants"]) >= 1


def test_gate_empty_tree_does_not_raise() -> None:
    lb = {"id": "E1", "name": "EMPTY", "tree": {"type": "empty", "children": []}, "parse_status": "failed"}
    resolved = build_resolved_logic_blocks([lb])
    assert len(resolved) == 1
    assert resolved[0]["gate_status"] == "needs_engineer"
    assert resolved[0]["tree"]["type"] == "empty"


def test_mcdc_planner_or_branches() -> None:
    rb = {
        "name": "SHUTOFF_DECISION",
        "tree": enrich_tree_with_atoms(dict(SHUTOFF_TREE)),
        "footnote_variants": [],
        "gate_status": "ready",
    }
    paths, meta = plan_test_paths(rb, control_name="SHUTOFF_DECISION", max_expansion_factor=32)
    assert not meta.get("aborted")
    assert len(paths) >= 2
    labels = {p["label"] for p in paths}
    assert any("branch" in lb for lb in labels)
