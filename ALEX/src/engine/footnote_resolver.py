"""Footnote registry and expansion into concrete atoms (no (*n) literals in resolved trees)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.footnote_conditional import given_lines_for_footnote_rule, parse_conditional_footnote
from src.parsers.two_column_table_parser import FOOTNOTE_RE

_FOOTNOTE_LINE_RE = re.compile(r"^\(\*(\d+)\)\s+(.+)$", re.I)


def build_footnote_registry(footnote_definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for row in footnote_definitions:
        ref = str(row.get("ref") or "").strip()
        if not ref:
            fn = row.get("footnote_num")
            if fn:
                ref = f"(*{fn})"
        body = str(row.get("definition") or row.get("raw_text") or "").strip()
        if not ref:
            continue
        parsed = row.get("parsed_conditional") or parse_conditional_footnote(body)
        entry = registry.setdefault(
            ref,
            {
                "ref": ref,
                "bodies": [],
                "parsed_rule": None,
                "condition_names": set(),
                "sources": [],
            },
        )
        if body:
            entry["bodies"].append(body)
        if parsed:
            entry["parsed_rule"] = parsed
        cn = str(row.get("condition_name") or "").strip()
        if cn:
            entry["condition_names"].add(cn)
        src = row.get("source")
        if src:
            entry["sources"].append(src)
    for ref, entry in registry.items():
        if not entry.get("parsed_rule") and entry.get("bodies"):
            entry["parsed_rule"] = parse_conditional_footnote(entry["bodies"][0])
        entry["condition_names"] = sorted(entry["condition_names"])
    return registry


def expand_footnote_variants(
    registry: dict[str, dict[str, Any]],
    ref: str,
) -> list[dict[str, Any]]:
    """Return variant dicts: {branch, given_lines, atoms[]}."""
    entry = registry.get(ref) or {}
    rule = entry.get("parsed_rule")
    if not rule:
        return []
    variants: list[dict[str, Any]] = []
    when_lines = given_lines_for_footnote_rule(rule, branch="when")
    if when_lines:
        variants.append(
            {
                "branch": "footnote_when",
                "footnote_ref": ref,
                "given_lines": when_lines,
                "atoms": _lines_to_atoms(when_lines),
            }
        )
    other_lines = given_lines_for_footnote_rule(rule, branch="otherwise")
    if other_lines:
        variants.append(
            {
                "branch": "footnote_otherwise",
                "footnote_ref": ref,
                "given_lines": other_lines,
                "atoms": _lines_to_atoms(other_lines),
            }
        )
    return variants


def _lines_to_atoms(lines: list[str]) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for line in lines:
        m = re.match(r"(?i)^\s*Given:\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", line.strip())
        if m:
            atoms.append(
                {
                    "signal": m.group(1).strip(),
                    "operator": "=",
                    "value": m.group(2).strip(),
                    "negated": False,
                    "footnote_refs": [],
                    "resolution": "resolved",
                }
            )
    return atoms


def apply_footnote_resolution_to_atoms(
    atoms: list[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    For atoms with footnote_refs, produce expanded variants.
    Returns (resolved_atoms, footnote_variant_specs).
    """
    resolved: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    for atom in atoms:
        refs = atom.get("footnote_refs") or []
        if not refs:
            resolved.append(atom)
            continue
        ref = str(refs[0])
        entry = registry.get(ref) or {}
        if entry.get("parsed_rule"):
            for v in expand_footnote_variants(registry, ref):
                variants.append({**v, "parent_signal": atom.get("signal")})
            atom = dict(atom)
            atom["resolution"] = "resolved"
            atom["footnote_expanded"] = True
            resolved.append(atom)
        else:
            atom = dict(atom)
            atom["resolution"] = "needs_llm"
            resolved.append(atom)
    return resolved, variants


def display_label_for_atom(atom: dict[str, Any]) -> str:
    sig = atom.get("signal", "?")
    val = atom.get("value")
    op = atom.get("operator", "==")
    neg = "NOT " if atom.get("negated") else ""
    if val is None:
        refs = atom.get("footnote_refs") or []
        if refs:
            return f"{neg}{sig} {op} {refs[0]}"
        return f"{neg}{sig}"
    return f"{neg}{sig} {op} {val}"
