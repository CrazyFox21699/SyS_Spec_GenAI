"""Build condition AST from raw text (best-effort, deterministic)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.logic_keywords import parse_edge_event


def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        ok = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                ok = False
                break
        if ok and depth == 0:
            s = s[1:-1].strip()
        else:
            break
    return s


def _split_top_level(s: str, sep: str) -> list[str] | None:
    """Split on sep (e.g. ' AND ') respecting parentheses."""
    s = _strip_outer_parens(s)
    sep_l = len(sep)
    parts: list[str] = []
    start = 0
    depth = 0
    i = 0
    while i <= len(s) - sep_l:
        if s[i] == "(":
            depth += 1
            i += 1
            continue
        if s[i] == ")":
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0 and s[i : i + sep_l].upper() == sep.upper():
            parts.append(s[start:i].strip())
            start = i + sep_l
            i = start
            continue
        i += 1
    tail = s[start:].strip()
    if parts:
        parts.append(tail)
        return [p for p in parts if p]
    return None


def _looks_like_compound(chunk: str) -> bool:
    """True when chunk contains top-level AND/OR (not a single leaf)."""
    inner = _strip_outer_parens(chunk)
    if _split_top_level(inner, " OR "):
        return True
    parts = _split_top_level(inner, " AND ")
    return bool(parts and len(parts) > 1)


def _parse_atom(chunk: str) -> dict[str, Any]:
    chunk = chunk.strip()
    if _looks_like_compound(chunk):
        return parse_condition_and_segment(chunk)
    edge = parse_edge_event(chunk)
    if edge:
        return {
            "type": "edge_event",
            "atom_kind": "edge_event",
            "from_state": edge["from_state"],
            "to_state": edge["to_state"],
            "requires_history": True,
            "raw_text": chunk,
        }
    m = re.match(
        r"^(.+?)\s*(==|!=|>=|<=|=|>|<)\s*(.+)$",
        chunk,
        re.DOTALL,
    )
    if not m:
        if re.search(r"(ms|elapsed|timeout|exceeded|not\s+elapsed)", chunk, re.I):
            return {"type": "timing_condition", "atom_kind": "timing_condition", "raw_text": chunk}
        if re.match(r"^Condition_[A-Za-z0-9_]+$", chunk) or re.match(r"^Cond(ition)?_[A-Za-z0-9_]+$", chunk, re.I):
            return {"type": "reference", "name": chunk}
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", chunk):
            return {
                "type": "boolean_predicate",
                "signal": chunk,
                "operator": "==",
                "value": "1",
                "raw_text": chunk,
            }
        return {"type": "opaque", "raw_text": chunk}

    left, op, right = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    if op == "=":
        op = "=="
    if re.search(r"(ms|s)\b|elapsed|timeout|exceeded|not\s+elapsed", left + right, re.I):
        return {
            "type": "timing_condition",
            "raw_text": chunk,
            "timer": left if re.match(r"^T\d*$", left, re.I) else None,
            "operator": op,
            "value": right,
        }
    return {
        "type": "signal_condition",
        "atom_kind": "state_condition",
        "signal": left,
        "operator": op,
        "value": right,
        "value_domain": _value_domain(right),
    }


def _value_domain(value: str) -> str:
    from src.engine.memory_semantics_parser import classify_value_domain

    return classify_value_domain(value)


def parse_condition_tree(raw: str) -> dict[str, Any]:
    """Parse into AND/OR tree; on failure return raw + failed status."""
    raw_clean = (raw or "").strip()
    if not raw_clean:
        return {"type": "empty", "parse_status": "failed", "raw_condition": raw}

    # NOT prefix
    if raw_clean.upper().startswith("NOT "):
        inner = parse_condition_tree(raw_clean[4:].strip())
        node = {"type": "NOT", "children": [inner], "raw_condition": raw_clean}
        return finalize_condition_tree(node)

    # Try OR first (lower precedence than AND in many specs — here split OR then AND inside each)
    or_parts = _split_top_level(raw_clean, " OR ")
    if or_parts and len(or_parts) > 1:
        children = [parse_condition_and_segment(p) for p in or_parts]
        node = {
            "type": "OR",
            "children": children,
            "raw_condition": raw_clean,
        }
        return finalize_condition_tree(node)
    return finalize_condition_tree(parse_condition_and_segment(raw_clean))


def _parse_and_child(part: str, depth: int) -> dict[str, Any]:
    part = part.strip()
    if part.upper().startswith("NOT ") or "(" in part:
        return parse_condition_and_segment(part, depth + 1)
    atom = _parse_atom(part)
    atom["raw_condition"] = part
    atom["parse_status"] = aggregate_tree_parse_status(atom)
    return atom


def parse_condition_and_segment(segment: str, _depth: int = 0) -> dict[str, Any]:
    if _depth > 12:
        return {"type": "opaque", "raw_text": segment, "parse_status": "failed"}
    segment = _strip_outer_parens(segment)
    if segment.upper().startswith("NOT "):
        inner = parse_condition_and_segment(segment[4:].strip(), _depth + 1)
        node = {"type": "NOT", "children": [inner], "raw_condition": segment}
        return finalize_condition_tree(node)
    or_parts = _split_top_level(segment, " OR ")
    if or_parts and len(or_parts) > 1:
        node = {
            "type": "OR",
            "children": [parse_condition_and_segment(p, _depth + 1) for p in or_parts],
            "raw_condition": segment,
        }
        return finalize_condition_tree(node)
    and_parts = _split_top_level(segment, " AND ")
    if and_parts and len(and_parts) > 1:
        node = {
            "type": "AND",
            "children": [_parse_and_child(p, _depth + 1) for p in and_parts],
            "raw_condition": segment,
        }
        return finalize_condition_tree(node)
    atom = _parse_atom(segment)
    atom["raw_condition"] = segment
    atom["parse_status"] = aggregate_tree_parse_status(atom)
    return atom


def tree_has_opaque(node: dict[str, Any]) -> bool:
    """True when any leaf is opaque or an unresolved reference."""
    t = str(node.get("type") or "")
    if t in ("opaque", "reference"):
        return True
    for ch in node.get("children") or []:
        if isinstance(ch, dict) and tree_has_opaque(ch):
            return True
    return False


def aggregate_tree_parse_status(node: dict[str, Any]) -> str:
    """Roll up ok / partial / failed from AST leaves."""
    t = str(node.get("type") or "")
    if t == "empty":
        return "failed"
    if t == "opaque":
        return "partial"
    if t == "reference":
        return "partial"
    children = [c for c in (node.get("children") or []) if isinstance(c, dict)]
    if children:
        child_statuses = [aggregate_tree_parse_status(c) for c in children]
        if any(s == "failed" for s in child_statuses):
            return "partial"
        if any(s == "partial" for s in child_statuses):
            return "partial"
        return "ok"
    if t in ("signal_condition", "boolean_predicate", "timing_condition", "condition"):
        return "ok"
    raw = str(node.get("parse_status") or "").strip().lower()
    if raw in ("ok", "partial", "failed"):
        return raw
    return "partial"


def finalize_condition_tree(node: dict[str, Any]) -> dict[str, Any]:
    """Set honest parse_status on composite nodes after parsing."""
    for ch in node.get("children") or []:
        if isinstance(ch, dict):
            finalize_condition_tree(ch)
    node["parse_status"] = aggregate_tree_parse_status(node)
    return node
