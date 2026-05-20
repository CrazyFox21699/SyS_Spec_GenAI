"""Build condition AST from raw text (best-effort, deterministic)."""

from __future__ import annotations

import re
from typing import Any


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


def _parse_atom(chunk: str) -> dict[str, Any]:
    chunk = chunk.strip()
    m = re.match(
        r"^(.+?)\s*(==|!=|>=|<=|=|>|<)\s*(.+)$",
        chunk,
        re.DOTALL,
    )
    if not m:
        if re.search(r"(ms|elapsed|timeout|exceeded|not\s+elapsed)", chunk, re.I):
            return {"type": "timing_condition", "raw_text": chunk}
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
    return {"type": "signal_condition", "signal": left, "operator": op, "value": right}


def parse_condition_tree(raw: str) -> dict[str, Any]:
    """Parse into AND/OR tree; on failure return raw + failed status."""
    raw_clean = (raw or "").strip()
    if not raw_clean:
        return {"type": "empty", "parse_status": "failed", "raw_condition": raw}

    # NOT prefix
    if raw_clean.upper().startswith("NOT "):
        inner = parse_condition_tree(raw_clean[4:].strip())
        return {"type": "NOT", "children": [inner], "raw_condition": raw_clean, "parse_status": "partial"}

    # Try OR first (lower precedence than AND in many specs — here split OR then AND inside each)
    or_parts = _split_top_level(raw_clean, " OR ")
    if or_parts and len(or_parts) > 1:
        children = [parse_condition_and_segment(p) for p in or_parts]
        return {
            "type": "OR",
            "children": children,
            "raw_condition": raw_clean,
            "parse_status": "partial",
        }
    return parse_condition_and_segment(raw_clean)


def parse_condition_and_segment(segment: str, _depth: int = 0) -> dict[str, Any]:
    if _depth > 12:
        return {"type": "opaque", "raw_text": segment, "parse_status": "failed"}
    segment = _strip_outer_parens(segment)
    and_parts = _split_top_level(segment, " AND ")
    if and_parts and len(and_parts) > 1:
        return {
            "type": "AND",
            "children": [
                _parse_atom(p) if "(" not in p else parse_condition_and_segment(p, _depth + 1)
                for p in and_parts
            ],
            "raw_condition": segment,
            "parse_status": "partial",
        }
    if "(" in segment or ")" in segment:
        inner = parse_condition_and_segment(segment, _depth + 1)
        if inner.get("type") not in ("signal_condition", "boolean_predicate", "timing_condition", "reference", "opaque", "empty"):
            return inner
    atom = _parse_atom(segment)
    atom["raw_condition"] = segment
    atom["parse_status"] = "ok"
    return atom
