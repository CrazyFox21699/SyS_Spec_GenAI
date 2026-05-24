"""Tests for Excel priority vs boolean decision mode."""

from __future__ import annotations

from src.engine.excel_priority_parser import annotate_logic_block_decision_mode, detect_decision_mode


def test_detect_boolean_default():
    assert detect_decision_mode(["A OR B AND C"]) == "boolean"


def test_detect_sequential_priority_phrase():
    mode = detect_decision_mode(
        ["If condition A is met, other conditions shall not be judged."]
    )
    assert mode == "sequential"


def test_annotate_logic_block():
    block = {"name": "CTRL", "raw_expression": "A OR B"}
    annotate_logic_block_decision_mode(
        block,
        ["If condition A is met, other conditions shall not be judged."],
    )
    assert block["decision_mode"] == "sequential"
