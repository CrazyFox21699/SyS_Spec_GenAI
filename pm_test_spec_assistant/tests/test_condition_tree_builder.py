from __future__ import annotations

from src.engine.condition_tree_builder import parse_condition_tree
from src.engine.logic_tree_renderer import render_tree_lines


def test_boolean_predicates_render_as_named_tree_leaves() -> None:
    raw = "(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)"

    tree = parse_condition_tree(raw)
    rendered = "\n".join(render_tree_lines(tree))

    assert tree["type"] == "AND"
    or_nodes = [c for c in tree.get("children") or [] if c.get("type") == "OR"]
    assert or_nodes, "expected nested OR branch for NORMAL_ROUTE / BACKUP_ROUTE"
    backup_and = next(
        (c for c in or_nodes[0].get("children") or [] if c.get("type") == "AND"),
        None,
    )
    assert backup_and is not None
    assert "PWR_REQ_VALID" in rendered
    assert "VEHICLE_SAFE" in rendered
    assert "NORMAL_ROUTE" in rendered
    assert "BACKUP_ROUTE" in rendered
    assert "T_SHUT_CONFIRM elapsed" in rendered
    assert "NOK_SHUTOFF" in rendered
    assert "opaque" not in rendered


def test_signal_only_atom_is_boolean_predicate() -> None:
    tree = parse_condition_tree("PWR_REQ_VALID")

    assert tree["type"] == "boolean_predicate"
    assert tree["signal"] == "PWR_REQ_VALID"
    assert tree["operator"] == "=="
    assert tree["value"] == "1"
    assert tree.get("parse_status") == "ok"


def test_opaque_leaf_marks_tree_partial() -> None:
    from src.engine.condition_tree_builder import aggregate_tree_parse_status, tree_has_opaque

    tree = parse_condition_tree("PWR_REQ_VALID AND some weird text !!!")
    assert tree_has_opaque(tree)
    assert aggregate_tree_parse_status(tree) == "partial"
