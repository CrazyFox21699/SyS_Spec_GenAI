"""Parse timer qualifiers embedded in condition clauses (T1 elapsed, continues for T1, …)."""

from __future__ import annotations

import re
from typing import Any

_SYMBOL_ELAPSED_RE = re.compile(
    r"^(?P<symbol>T[A-Za-z0-9_]+)\s+(?P<qualifier>elapsed|not\s+elapsed|timeout|exceeded)\b",
    re.I,
)
_QUALIFIED_ELAPSED_RE = re.compile(
    r"(?P<qualified>.+?)\s+(?P<symbol>T[A-Za-z0-9_]+)\s+(?P<qualifier>elapsed|not\s+elapsed)\s*$",
    re.I,
)
_CONTINUES_FOR_RE = re.compile(r"\bcontinues\s+for\s+(?P<symbol>T[A-Za-z0-9_]+)\b", re.I)
_OR_MORE_AFTER_RE = re.compile(
    r"\b(?P<symbol>T[A-Za-z0-9_]+)\s+or\s+more\s+after\b",
    re.I,
)
_TIMING_VALUE_RE = re.compile(r"(\d+)\s*\[(\w+)\](?:\s+(\d+))?")


def parse_timer_qualifier(text: str) -> dict[str, Any] | None:
    """Return timer_qualified metadata when text matches a timer pattern."""
    raw = str(text or "").strip()
    if not raw:
        return None

    m = _SYMBOL_ELAPSED_RE.match(raw)
    if m:
        return {
            "type": "timer_qualified",
            "timer_symbol": m.group("symbol").upper(),
            "qualifier": m.group("qualifier").lower().replace("  ", " "),
            "qualified_condition": None,
            "raw_text": raw,
        }

    m = _QUALIFIED_ELAPSED_RE.match(raw)
    if m:
        return {
            "type": "timer_qualified",
            "timer_symbol": m.group("symbol").upper(),
            "qualifier": m.group("qualifier").lower().replace("  ", " "),
            "qualified_condition": m.group("qualified").strip(),
            "raw_text": raw,
        }

    m = _CONTINUES_FOR_RE.search(raw)
    if m:
        return {
            "type": "timer_qualified",
            "timer_symbol": m.group("symbol").upper(),
            "qualifier": "continues_for",
            "qualified_condition": raw,
            "raw_text": raw,
        }

    m = _OR_MORE_AFTER_RE.search(raw)
    if m:
        return {
            "type": "timer_qualified",
            "timer_symbol": m.group("symbol").upper(),
            "qualifier": "or_more_after",
            "qualified_condition": raw,
            "raw_text": raw,
        }

    if re.search(r"\belapsed\b|\btimeout\b|\bnot\s+elapsed\b", raw, re.I) and re.search(
        r"\bT[A-Za-z0-9_]+\b", raw
    ):
        sym = re.search(r"\b(T[A-Za-z0-9_]+)\b", raw)
        return {
            "type": "timer_qualified",
            "timer_symbol": sym.group(1).upper() if sym else None,
            "qualifier": "elapsed",
            "qualified_condition": raw,
            "raw_text": raw,
        }
    return None


def build_timing_constant_index(condition_definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map timer symbol names to constant table rows (unit, tolerance)."""
    index: dict[str, dict[str, Any]] = {}
    for row in condition_definitions or []:
        name = str(row.get("name") or "").strip().upper()
        if not name:
            continue
        definition = str(row.get("definition") or row.get("constant_value") or "")
        parsed_hint = str(row.get("constant_value") or row.get("parsed_hint") or "")
        blob = " ".join(x for x in (definition, parsed_hint) if x)
        m = _TIMING_VALUE_RE.search(blob)
        entry: dict[str, Any] = {
            "name": name,
            "definition": definition,
            "source": row.get("source"),
        }
        if m:
            entry["duration"] = int(m.group(1))
            entry["unit"] = m.group(2)
            if m.group(3):
                entry["tolerance"] = int(m.group(3))
        index[name] = entry
    return index


def _attach_constant(meta: dict[str, Any], constant_index: dict[str, dict[str, Any]]) -> None:
    sym = str(meta.get("timer_symbol") or "").upper()
    if sym and sym in constant_index:
        meta["constant_ref"] = constant_index[sym]


def enrich_ast_node(node: dict[str, Any], constant_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Recursively enrich AST nodes with timer_qualified metadata (additive)."""
    if not isinstance(node, dict):
        return node
    t = node.get("type")
    if t in ("AND", "OR", "NOT"):
        children = node.get("children") or []
        node["children"] = [enrich_ast_node(ch, constant_index) for ch in children if isinstance(ch, dict)]
        return node

    name = str(node.get("name") or node.get("raw_text") or "")
    meta = parse_timer_qualifier(name)
    if meta:
        node["type"] = "timing_condition"
        node["atom_kind"] = "timing_condition"
        node["timer_qualified"] = meta
        _attach_constant(meta, constant_index)
    return node


def enrich_logic_blocks(
    logic_blocks: list[dict[str, Any]],
    condition_definitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach timer metadata to logic block trees without changing raw_expression."""
    constant_index = build_timing_constant_index(condition_definitions)
    for lb in logic_blocks:
        tree = lb.get("tree")
        if isinstance(tree, dict):
            lb["tree"] = enrich_ast_node(tree, constant_index)
        timers = []
        raw = str(lb.get("raw_expression") or "")
        for part in re.split(r"\s+AND\s+|\s+OR\s+", raw, flags=re.I):
            meta = parse_timer_qualifier(part.strip())
            if meta:
                _attach_constant(meta, constant_index)
                timers.append(meta)
        if timers:
            lb["timer_qualifiers"] = timers
    return logic_blocks
