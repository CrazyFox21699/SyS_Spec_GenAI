"""Tests for lifecycle keyword registry and state grammar parser."""

from __future__ import annotations

from src.engine.condition_tree_builder import parse_condition_tree
from src.engine.logic_keywords import normalize_lifecycle_label, parse_edge_event
from src.engine.state_grammar_parser import (
    parse_state_blocks_from_paragraphs,
    parse_state_blocks_from_tables,
)


def test_normalize_lifecycle_labels():
    assert normalize_lifecycle_label("Get Started") == "start"
    assert normalize_lifecycle_label("Finish") == "finish"
    assert normalize_lifecycle_label("Initial value") == "initial_value"
    assert normalize_lifecycle_label("ACC = ON") is None


def test_parse_edge_event_binary():
    edge = parse_edge_event("OFF → ON")
    assert edge is not None
    assert edge["from_state"].upper() == "OFF"
    assert edge["to_state"].upper() == "ON"


def test_parse_state_blocks_from_paragraphs():
    lines = [
        "State PWR_MODE:",
        "Initial value = OFF",
        "Get Started: ACC OFF → ON",
        "Finish: PWR_MODE := OFF",
    ]
    blocks = parse_state_blocks_from_paragraphs(lines, {"file": "t.docx"})
    assert len(blocks) == 1
    block = blocks[0]
    assert block["state"] == "PWR_MODE"
    assert block["initial_value"] == "OFF"
    assert block["start_expression"]
    assert block["finish_expression"]


def test_parse_state_blocks_from_tables():
    grid = [
        ["Control", "Condition"],
        ["PWR_MODE", "Initial value"],
        ["", "OFF"],
        ["Get Started", "ACC OFF → ON"],
        ["Finish", "ACC ON → OFF"],
    ]
    blocks = parse_state_blocks_from_tables([{"grid": grid, "source": {"file": "t.docx"}}])
    assert len(blocks) == 1
    assert blocks[0]["state"] == "PWR_MODE"
    assert blocks[0]["initial_value"] == "OFF"
    assert blocks[0]["start_condition"]["to_state"].upper() == "ON"


def test_condition_tree_edge_event_atom():
    tree = parse_condition_tree("ACC OFF → ON")
    assert tree.get("type") == "edge_event"
    assert tree.get("atom_kind") == "edge_event"
    assert tree.get("requires_history") is True
