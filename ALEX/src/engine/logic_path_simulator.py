"""Deterministic what-if evaluation for parsed logic ASTs."""

from __future__ import annotations

import re
from typing import Any


def _norm_signal(name: str) -> str:
    return str(name or "").strip().upper()


def _coerce_value(raw: Any) -> str | float | int | bool:
    if raw is None:
        return ""
    text = str(raw).strip()
    if text.lower() in ("true", "1", "on", "yes"):
        return 1
    if text.lower() in ("false", "0", "off", "no"):
        return 0
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _compare(left: Any, op: str, right: Any) -> bool | None:
    if op in ("==", "="):
        return str(left).strip().lower() == str(right).strip().lower()
    if op == "!=":
        return str(left).strip().lower() != str(right).strip().lower()
    try:
        lnum = float(left)
        rnum = float(right)
    except (TypeError, ValueError):
        return None
    if op == ">":
        return lnum > rnum
    if op == ">=":
        return lnum >= rnum
    if op == "<":
        return lnum < rnum
    if op == "<=":
        return lnum <= rnum
    return None


def collect_simulation_signals(tree: dict[str, Any]) -> list[dict[str, str]]:
    """Unique signals referenced in the AST for path simulator inputs."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []

    def walk(node: dict[str, Any]) -> None:
        t = node.get("type")
        if t in ("AND", "OR", "NOT"):
            for ch in node.get("children") or []:
                if isinstance(ch, dict):
                    walk(ch)
            return
        if t == "signal_condition":
            sig = _norm_signal(node.get("signal"))
            if sig and sig not in seen:
                seen.add(sig)
                out.append({"signal": sig, "default": str(node.get("value") or "0")})
        elif t == "boolean_predicate":
            sig = _norm_signal(node.get("signal"))
            if sig and sig not in seen:
                seen.add(sig)
                out.append({"signal": sig, "default": "1"})
        elif t == "timing_condition":
            raw = str(node.get("raw_text") or "")
            for m in re.finditer(r"\b([A-Z][A-Z0-9_]+)\b", raw):
                sig = m.group(1)
                if sig not in seen and sig not in {"AND", "OR", "NOT", "MS"}:
                    seen.add(sig)
                    out.append({"signal": sig, "default": "0"})
        elif t == "condition":
            sig = _norm_signal(node.get("name"))
            if sig and sig not in seen:
                seen.add(sig)
                out.append({"signal": sig, "default": "1"})

    walk(tree)
    return out


def simulate_logic_path(tree: dict[str, Any], assignments: dict[str, Any]) -> dict[str, Any]:
    """Evaluate AST with signal assignments; returns result + active path nodes."""
    norm_assign = {_norm_signal(k): _coerce_value(v) for k, v in assignments.items()}
    active_nodes: list[str] = []
    unknown_nodes: list[str] = []

    def eval_node(node: dict[str, Any], node_id: str = "root") -> bool | None:
        t = node.get("type")
        if t in ("AND", "OR", "NOT"):
            children = [c for c in (node.get("children") or []) if isinstance(c, dict)]
            if t == "NOT":
                if not children:
                    unknown_nodes.append(node_id)
                    return None
                inner = eval_node(children[0], f"{node_id}.0")
                if inner is None:
                    unknown_nodes.append(node_id)
                    return None
                result = not inner
                if result:
                    active_nodes.append(node_id)
                return result
            results: list[bool | None] = []
            for i, ch in enumerate(children):
                results.append(eval_node(ch, f"{node_id}.{i}"))
            if any(r is None for r in results):
                unknown_nodes.append(node_id)
                return None
            bools = [bool(r) for r in results]
            result = all(bools) if t == "AND" else any(bools)
            if result:
                active_nodes.append(node_id)
            return result

        if t == "signal_condition":
            sig = _norm_signal(node.get("signal"))
            val = norm_assign.get(sig, _coerce_value(node.get("value")))
            cmp = _compare(val, str(node.get("operator") or "=="), node.get("value"))
            if cmp is None:
                unknown_nodes.append(node_id)
                return None
            if cmp:
                active_nodes.append(node_id)
            return cmp

        if t == "boolean_predicate":
            sig = _norm_signal(node.get("signal"))
            val = norm_assign.get(sig, 1)
            expected = _coerce_value(node.get("value") or "1")
            cmp = _compare(val, "==", expected)
            if cmp is None:
                unknown_nodes.append(node_id)
                return None
            if cmp:
                active_nodes.append(node_id)
            return cmp

        if t == "timing_condition":
            unknown_nodes.append(node_id)
            return None

        if t == "reference":
            unknown_nodes.append(node_id)
            return None

        if t == "opaque":
            unknown_nodes.append(node_id)
            return None

        if t == "condition":
            name = _norm_signal(node.get("name"))
            val = norm_assign.get(name, 1)
            cmp = _compare(val, "==", 1)
            if cmp is None:
                unknown_nodes.append(node_id)
                return None
            if cmp:
                active_nodes.append(node_id)
            return cmp

        unknown_nodes.append(node_id)
        return None

    outcome = eval_node(tree)
    status = "unknown"
    if outcome is True:
        status = "active"
    elif outcome is False:
        status = "inactive"

    return {
        "status": status,
        "result": outcome,
        "active_node_ids": active_nodes,
        "unknown_node_ids": unknown_nodes,
        "signals": collect_simulation_signals(tree),
    }
