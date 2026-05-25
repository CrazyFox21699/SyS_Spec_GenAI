"""Tests for timer qualifier parsing and AST enrichment."""

from __future__ import annotations

from src.engine.timer_qualifier_parser import (
    build_timing_constant_index,
    enrich_ast_node,
    enrich_logic_blocks,
    parse_timer_qualifier,
)


def test_parse_timer_symbol_elapsed():
    meta = parse_timer_qualifier("T_SHUT_CONFIRM elapsed")
    assert meta is not None
    assert meta["timer_symbol"] == "T_SHUT_CONFIRM"
    assert meta["qualifier"] == "elapsed"


def test_parse_qualified_condition_elapsed():
    meta = parse_timer_qualifier("ACC = ON AND T1 elapsed")
    assert meta is not None
    assert meta["timer_symbol"] == "T1"


def test_build_timing_constant_index():
    defs = [
        {"name": "T1", "definition": "700 [ms] 20", "constant_value": "700 [ms] 20"},
    ]
    idx = build_timing_constant_index(defs)
    assert idx["T1"]["duration"] == 700
    assert idx["T1"]["unit"] == "ms"


def test_enrich_logic_blocks_adds_timer_qualifiers():
    blocks = [
        {
            "name": "SHUTOFF",
            "raw_expression": "A AND T_SHUT_CONFIRM elapsed",
            "tree": {
                "type": "AND",
                "children": [
                    {"type": "condition", "name": "A"},
                    {"type": "condition", "name": "T_SHUT_CONFIRM elapsed"},
                ],
            },
        }
    ]
    defs = [{"name": "T_SHUT_CONFIRM", "definition": "500 [ms]"}]
    enrich_logic_blocks(blocks, defs)
    assert blocks[0].get("timer_qualifiers")
    leaf = blocks[0]["tree"]["children"][1]
    assert leaf.get("type") == "timing_condition"
    assert leaf.get("timer_qualified", {}).get("timer_symbol") == "T_SHUT_CONFIRM"
