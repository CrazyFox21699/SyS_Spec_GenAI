from __future__ import annotations

from src.engine.gate_spine_ast import build_gate_spine_ast
from src.engine.condition_tree_builder import tree_has_opaque
from src.engine.logic_tree_renderer import render_tree_lines


def test_gate_spine_ast_merges_detail_timing_into_leaf() -> None:
    rows = [
        {"token": "AND", "detail": "", "source": {"row": 1}},
        {"token": "PWR_REQ_VALID", "detail": "", "source": {"row": 2}},
        {"token": "OR", "detail": "", "source": {"row": 3}},
        {"token": "NORMAL_ROUTE", "detail": "", "source": {"row": 4}},
        {"token": "AND", "detail": "", "source": {"row": 5}},
        {"token": "BACKUP_ROUTE", "detail": "", "source": {"row": 6}},
        {"token": "T_SHUT_CONFIRM", "detail": "elapsed", "source": {"row": 7}},
        {"token": "NOT", "detail": "", "source": {"row": 8}},
        {"token": "NOK_SHUTOFF", "detail": "", "source": {"row": 9}},
    ]

    tree = build_gate_spine_ast(rows)
    rendered = "\n".join(render_tree_lines(tree))

    assert tree.get("type") == "AND"
    assert not tree_has_opaque(tree)
    assert "T_SHUT_CONFIRM elapsed" in rendered
    assert "NORMAL_ROUTE" in rendered
    assert "BACKUP_ROUTE" in rendered
