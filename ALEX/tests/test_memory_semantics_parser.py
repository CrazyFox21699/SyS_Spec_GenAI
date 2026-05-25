"""Tests for multivalued sentinel values and retention rules."""

from __future__ import annotations

from src.engine.logic_atom import parse_token_to_atom
from src.engine.memory_semantics_parser import (
    classify_value_domain,
    enrich_condition_definitions,
    parse_retention_rules,
)


def test_classify_sentinel_none():
    assert classify_value_domain("None") == "sentinel"
    assert classify_value_domain("Invalid") == "sentinel"


def test_parse_retention_rule():
    rules = parse_retention_rules(
        ["If communication is invalid, retain the previous confirmed value."],
        {"file": "spec.docx"},
    )
    assert len(rules) == 1
    assert rules[0]["rule_kind"] == "retain_previous"
    assert rules[0]["executable"] is False


def test_logic_atom_preserves_sentinel():
    atom = parse_token_to_atom("Vehicle speed = None")
    assert atom["value"] == "None"
    assert atom.get("value_domain") == "sentinel"


def test_enrich_condition_definitions():
    rows = [{"name": "X", "definition": "speed == None"}]
    enrich_condition_definitions(rows)
    assert rows[0].get("value_domain") == "sentinel"
