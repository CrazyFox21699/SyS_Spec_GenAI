"""Tests for logic-spec structural classifier."""

from __future__ import annotations

from src.classifiers.logic_spec_classifier import classify_logic_spec


def test_classify_logic_spec_with_control_table():
    text = "Generic control specification"
    tables = [[["Control", "Condition"], ["SHUTOFF", "AND ACC = ON"]]]
    result = classify_logic_spec(text, table_samples=tables)
    assert result["is_logic_spec"] is True
    assert result["score"] >= 0.35
    assert "logic_ops_in_tables" in result["signals"]


def test_classify_non_logic_narrative():
    result = classify_logic_spec("This is a project memo with no tables or logic keywords.")
    assert result["is_logic_spec"] is False
    assert result["score"] < 0.35
