"""Tests for multi-format spec support (ACC / signal / lifecycle)."""

from __future__ import annotations

from src.engine.control_cell_classifier import classify_control_cell
from src.engine.diagram_edge_classifier import classify_diagram_edge_label
from src.engine.indentation_ast_parser import ast_to_expression, paths_to_ast
from src.engine.lifecycle_transition_builder import lifecycle_to_transitions
from src.engine.logic_atom import enrich_table_ast_with_atoms
from src.engine.transition_logic_linker import infer_transition_logic_links
from src.parsers.signal_table_parser import parse_signal_grid, parse_signal_value_map
from src.parsers.two_column_table_parser import parse_control_condition_grid


def test_inner_or_three_leaves_under_and():
    paths = [
        ["OR", "A = 1"],
        ["OR", "AND", "B = 1"],
        ["OR", "AND", "OR", "C = 1"],
        ["OR", "AND", "OR", "D = 1"],
        ["OR", "AND", "OR", "E = 1"],
    ]
    ast, _ = paths_to_ast(paths, {"file": "test"})
    expr = ast_to_expression(ast)
    assert "A = 1" in expr
    assert "C = 1" in expr and "D = 1" in expr and "E = 1" in expr


def test_branch_groups_split_and_with_three_leaves():
    paths = [
        ["OR", "AND", "X = 1"],
        ["OR", "AND", "Y = 2"],
        ["OR", "AND", "Z = 3"],
    ]
    groups = ["g1", "g1", "g1"]
    ast, _ = paths_to_ast(paths, {"file": "test"}, branch_groups=groups)
    expr = ast_to_expression(ast)
    assert "X = 1" in expr and "Y = 2" in expr and "Z = 3" in expr


def test_transition_outcome_control_metadata():
    grid = [
        ["Control", "Condition"],
        ["No transitions → Yes", "OR", "ACC = Disabled"],
        ["No transitions → Yes", "OR", "AND", "ACC = Enabled"],
    ]
    tables = parse_control_condition_grid(grid, {"file": "acc.docx"}, table_id="T1")
    assert tables
    t = tables[0]
    assert t.source.get("kind") == "transition_outcome"
    assert "Yes" in str(t.source.get("to_state") or "")


def test_signal_table_parser_columns():
    grid = [
        ["Signal Name", "Description", "Sender", "Possible values and meanings", "Initial Received Value", "Fail Safe Value"],
        ["STLK", "Steering Lock", "IDA", "• 0: No Request\n• 1: On request", "0", "0"],
    ]
    signals = parse_signal_grid(grid, {"file": "sig.xlsx"})
    assert len(signals) == 1
    assert signals[0]["name"] == "STLK"
    assert signals[0]["sender"] == "IDA"
    assert signals[0]["initial_value"] == "0"
    assert len(signals[0]["values"]) == 2


def test_parse_signal_value_map():
    rows = parse_signal_value_map("• 0: No Request\n• 1: On request")
    assert rows[0]["value"] == "0"
    assert rows[1]["value"] == "1"


def test_edge_atom_enrichment():
    ast = {
        "type": "OR",
        "children": [
            {"type": "condition", "name": "OFF → ON", "raw_text": "OFF → ON", "footnotes": []},
        ],
    }
    enriched = enrich_table_ast_with_atoms(ast)
    leaf = enriched["children"][0]
    assert leaf.get("type") == "edge_event"
    assert leaf.get("from_state") == "OFF"


def test_lifecycle_to_transitions():
    sms = [
        {
            "state_name": "PWR_MODE",
            "start_condition": {"from_state": "OFF", "to_state": "ON", "raw": "OFF → ON"},
            "source": {"file": "spec.docx"},
        }
    ]
    trans = lifecycle_to_transitions(sms)
    assert trans and trans[0]["derivation"] == "lifecycle_grammar"


def test_diagram_edge_classifier():
    role = classify_diagram_edge_label("Transition Trigger Conditions")
    assert role["role"] == "trigger"


def test_infer_transition_logic_link():
    transitions = [{"raw_condition": "evaluate SHUTOFF_DECISION ok path", "from_state": "A", "to_state": "B"}]
    blocks = [{"id": "LB1", "name": "SHUTOFF_DECISION"}]
    linked = infer_transition_logic_links(transitions, blocks)
    assert linked[0].get("inferred_logic_id") == "LB1"


def test_lifecycle_control_skipped_from_logic_paths():
    grid = [
        ["Control", "Condition"],
        ["Get Started", "ACC OFF → ON"],
        ["SHUTOFF", "OR", "A = 1"],
    ]
    tables = parse_control_condition_grid(grid, {"file": "t.docx"}, table_id="T1")
    names = [t.control_name for t in tables]
    assert "Get Started" not in names
    assert any("SHUTOFF" in n for n in names)
