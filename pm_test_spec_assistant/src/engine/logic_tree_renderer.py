"""Render logic AST as tree view and flat Excel rows."""

from __future__ import annotations

from typing import Any


def render_tree_lines(node: dict[str, Any], prefix: str = "", is_last: bool = True) -> list[str]:
    """ASCII tree lines for UI."""
    connector = "└── " if is_last else "├── "
    t = node.get("type", "?")
    label = node.get("name") or t
    if t == "condition":
        label = node.get("name", "")
    lines = [f"{prefix}{connector}{label}"]
    children = node.get("children") or []
    ext = "    " if is_last else "│   "
    for i, ch in enumerate(children):
        lines.extend(render_tree_lines(ch, prefix + ext, i == len(children) - 1))
    if not children and prefix == "":
        lines = [label]
    return lines


def _node_css_class(node: dict[str, Any]) -> str:
    t = node.get("type", "")
    if t == "AND":
        return "logic-and"
    if t == "OR":
        return "logic-or"
    if t == "NOT":
        return "logic-not"
    if node.get("issue_status") == "review_required" or node.get("review_status") == "blocked":
        return "logic-unresolved"
    if node.get("source_type") == "llm_generated":
        return "logic-llm"
    return "logic-ref"


def tree_view_data(
    tree_id: str,
    node: dict[str, Any],
    *,
    parent_id: str | None = None,
    depth: int = 0,
) -> list[dict[str, Any]]:
    """Structured nodes for web tree viewer."""
    nid = node.get("id") or f"{tree_id}_d{depth}"
    rows = [
        {
            "tree_id": tree_id,
            "node_id": nid,
            "parent_node_id": parent_id,
            "depth": depth,
            "node_type": node.get("type"),
            "operator": node.get("type") if node.get("type") in ("AND", "OR", "NOT") else "",
            "condition_name": node.get("name") if node.get("type") == "condition" else "",
            "raw_text": node.get("raw_text", ""),
            "normalized_text": node.get("name") or node.get("raw_text", ""),
            "source": node.get("source"),
            "parser_reason": node.get("parser_reason", ""),
            "confidence": node.get("confidence", "medium"),
            "review_status": node.get("review_status", "pending"),
            "issue_status": node.get("issue_status", "ok"),
            "css_class": _node_css_class(node),
        }
    ]
    for ch in node.get("children") or []:
        rows.extend(tree_view_data(tree_id, ch, parent_id=nid, depth=depth + 1))
    return rows


def flatten_ast_to_rows(tree_id: str, node: dict[str, Any], parent_id: str | None = None, depth: int = 0) -> list[dict[str, Any]]:
    return tree_view_data(tree_id, node, parent_id=parent_id, depth=depth)
