"""Build condition AST directly from Excel/Word gate-spine token rows (table-native)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.condition_tree_builder import _parse_atom, finalize_condition_tree
from src.engine.logic_keywords import is_logic_gate

_TIMING_HINT = re.compile(r"(elapsed|timeout|exceeded|not\s+elapsed|\bms\b|\bs\b)", re.I)


def _leaf_text(token: str, detail: str) -> str:
    """Combine condition token with Detail column when detail adds timing/value."""
    tok = str(token or "").strip()
    det = str(detail or "").strip()
    if not tok:
        return det
    if not det:
        return tok
    if det.upper() in {"AND", "OR", "NOT"}:
        return tok
    if tok.upper() == det.upper() or det.upper() in tok.upper():
        return tok
    if _TIMING_HINT.search(det) or re.match(r"^T\d", det, re.I):
        return f"{tok} {det}".strip()
    if re.match(r"^(==|!=|>=|<=|=|>|<)", det):
        return f"{tok} {det}".strip()
    return tok


def _leaf_node(token: str, detail: str, *, source: dict[str, Any] | None = None) -> dict[str, Any]:
    text = _leaf_text(token, detail)
    node = _parse_atom(text)
    node["raw_condition"] = text
    node["table_token"] = str(token or "").strip()
    if detail:
        node["detail"] = str(detail).strip()
    if source:
        node["source"] = dict(source)
    return node


def build_gate_spine_ast(
    rows: list[dict[str, Any]],
    *,
    default_gate: str = "AND",
) -> dict[str, Any]:
    """
    Build AST from gate-spine table rows (token + optional detail per row).

    Each row: {token, detail?, source?, row_no?}
    """
    root_gate = default_gate.upper()
    root_parts: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    def close_to(level: int) -> None:
        nonlocal groups, root_parts
        while len(groups) > level:
            grp = groups.pop()
            gate = str(grp.get("gate") or "AND").upper()
            parts = list(grp.get("parts") or [])
            if not parts:
                continue
            combined = _combine_nodes(gate, parts)
            if groups:
                groups[-1].setdefault("parts", []).append(combined)
            else:
                root_parts.append(combined)

    for row in rows or []:
        token = str(row.get("token") or "").strip()
        if not token:
            continue
        upper = token.upper()
        if is_logic_gate(token):
            if not root_gate or root_gate == "AND" and upper in {"AND", "OR", "NOT"} and not root_parts and not groups:
                root_gate = upper
                continue
            if upper == root_gate:
                if groups and str(groups[-1].get("gate") or "") != root_gate:
                    groups.append({"gate": upper, "parts": []})
                else:
                    close_to(0)
                continue
            groups.append({"gate": upper, "parts": []})
            continue
        if groups and len(groups[-1].get("parts") or []) >= 2:
            close_to(0)
        leaf = _leaf_node(token, str(row.get("detail") or ""), source=row.get("source"))
        if groups:
            groups[-1].setdefault("parts", []).append(leaf)
        else:
            root_parts.append(leaf)

    close_to(0)
    if not root_parts:
        return {"type": "empty", "parse_status": "failed", "raw_condition": ""}
    tree = _combine_nodes(root_gate, root_parts)
    tree["raw_condition"] = ""
    return finalize_condition_tree(tree)


def _combine_nodes(gate: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
    gate = (gate or "AND").upper()
    items = [p for p in parts if isinstance(p, dict)]
    if not items:
        return {"type": "empty", "parse_status": "failed"}
    if gate == "NOT":
        inner = items[0] if len(items) == 1 else _combine_nodes("AND", items)
        return finalize_condition_tree({"type": "NOT", "children": [inner]})
    if len(items) == 1:
        return items[0]
    return finalize_condition_tree({"type": gate, "children": items})
