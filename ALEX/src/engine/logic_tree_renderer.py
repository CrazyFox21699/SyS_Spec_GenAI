"""Render logic AST as tree view and flat Excel rows."""

from __future__ import annotations

from typing import Any


def render_tree_lines(node: dict[str, Any], prefix: str = "", is_last: bool = True) -> list[str]:
    """ASCII tree lines for UI."""
    connector = "└── " if is_last else "├── "
    t = node.get("type", "?")
    label = node.get("name") or node.get("raw_text") or t
    if t == "condition":
        label = node.get("name", "")
    elif t in ("signal_condition", "boolean_predicate"):
        sig = str(node.get("signal") or "").strip()
        op = str(node.get("operator") or "").strip()
        val = str(node.get("value") or "").strip()
        label = sig if t == "boolean_predicate" else " ".join(p for p in (sig, op, val) if p)
    elif t == "timing_condition":
        tq = node.get("timer_qualified") if isinstance(node.get("timer_qualified"), dict) else {}
        sym = tq.get("timer_symbol") or ""
        label = node.get("raw_text") or (f"{sym} {tq.get('qualifier', 'elapsed')}".strip() if sym else label)
    elif t == "edge_event":
        label = f"{node.get('from_state', '')} → {node.get('to_state', '')}".strip() or label
    elif t == "opaque":
        label = node.get("raw_text") or label
    lines = [f"{prefix}{connector}{label}"]
    children = node.get("children") or []
    ext = "    " if is_last else "│   "
    for i, ch in enumerate(children):
        lines.extend(render_tree_lines(ch, prefix + ext, i == len(children) - 1))
    if not children and prefix == "":
        lines = [label]
    return lines


def _source_row_no(source: Any) -> int | None:
    if not isinstance(source, dict):
        return None
    for key in ("row_no", "row", "row_hint"):
        val = source.get(key)
        if val is None or val == "":
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def _node_css_class(node: dict[str, Any]) -> str:
    t = node.get("type", "")
    if t == "edge_event":
        return "logic-edge"
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
    if t == "boolean_predicate":
        return "logic-ref"
    if t == "timing_condition":
        return "logic-timer"
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
            "gate": node.get("type") if node.get("type") in ("AND", "OR", "NOT") else "",
            "condition_name": node.get("name")
            if node.get("type") in ("condition", "edge_event")
            else node.get("signal", ""),
            "signal": node.get("signal", ""),
            "operator": node.get("operator", ""),
            "value": node.get("value", ""),
            "raw_text": node.get("raw_text", ""),
            "atom_kind": node.get("atom_kind") or node.get("type", ""),
            "timer_qualified": node.get("timer_qualified"),
            "requires_history": node.get("requires_history", False),
            "value_domain": node.get("value_domain", ""),
            "normalized_text": node.get("name") or node.get("signal") or node.get("raw_text", ""),
            "source": node.get("source"),
            "source_row": _source_row_no(node.get("source")),
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
