from __future__ import annotations

from src.engine.logic_tree_renderer import flatten_ast_to_rows


def test_flatten_ast_includes_source_row_from_node_source() -> None:
    tree = {
        "id": "root",
        "type": "OR",
        "children": [
            {
                "id": "leaf1",
                "type": "boolean_predicate",
                "signal": "OK_SHUTOFF",
                "source": {"row_no": 4, "file": "spec.docx"},
            }
        ],
    }
    rows = flatten_ast_to_rows("TC2_T1", tree)
    leaf = next(r for r in rows if r.get("signal") == "OK_SHUTOFF")
    assert leaf.get("source_row") == 4
    assert leaf.get("css_class") == "logic-ref"
