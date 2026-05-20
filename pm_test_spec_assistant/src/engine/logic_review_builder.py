"""Build unified Logic Review items for web UI (one control = one review card)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.indentation_ast_parser import ast_to_expression
from src.engine.logic_tree_renderer import flatten_ast_to_rows, render_tree_lines

TERM_RE = re.compile(r"\b[A-Z][A-Z0-9_=]+\b")
_IGNORE_TERMS = {"AND", "OR", "NOT", "TRUE", "FALSE"}


def _normalize_term(term: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(term or "").upper())


def _lookup_rows(index: dict[str, list[dict[str, Any]]], term: str) -> list[dict[str, Any]]:
    rows = list(index.get(term, []))
    norm = _normalize_term(term)
    if norm and norm != term:
        seen = {
            (
                str(row.get("name") or ""),
                str(row.get("definition") or ""),
                str((row.get("source") or {}).get("file") or ""),
            )
            for row in rows
        }
        for row in index.get(norm, []):
            key = (
                str(row.get("name") or ""),
                str(row.get("definition") or ""),
                str((row.get("source") or {}).get("file") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def _match_mode(term: str, row: dict[str, Any]) -> str:
    name = str(row.get("name") or "").strip()
    if not name:
        return "unknown"
    if name == term:
        return "exact"
    if _normalize_term(name) == _normalize_term(term):
        return "normalized"
    return "related"


def _format_source(src: dict[str, Any] | None) -> str:
    if not src:
        return ""
    parts = [
        src.get("file") or src.get("document") or "",
        src.get("sheet") or "",
        src.get("table") or src.get("table_id") or "",
        f"row {src.get('row')}" if src.get("row") else "",
    ]
    return " / ".join(p for p in parts if p)


def _clip(text: Any, limit: int = 120) -> str:
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 3].rstrip() + "..."


def _collect_terms(lb: dict[str, Any], expression: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in lb.get("unresolved_refs") or []:
        t = str(term or "").strip()
        if t and t not in seen:
            seen.add(t)
            terms.append(t)
    for match in TERM_RE.findall(expression or ""):
        if match in _IGNORE_TERMS or match in seen:
            continue
        seen.add(match)
        terms.append(match)
    return terms


def _trace_row(
    term: str,
    *,
    control_name: str,
    defs_by_name: dict[str, list[dict[str, Any]]],
    supplemental_defs_by_name: dict[str, list[dict[str, Any]]],
    blocks_by_name: dict[str, dict[str, Any]],
    aliases_by_target: dict[str, list[dict[str, Any]]],
    aliases_by_alias: dict[str, list[dict[str, Any]]],
    footnotes_by_condition: dict[str, list[dict[str, Any]]],
    engineer_defs_by_name: dict[str, list[dict[str, Any]]],
    unresolved_terms: set[str],
) -> dict[str, Any]:
    defs = _lookup_rows(defs_by_name, term)
    supplemental_defs = _lookup_rows(supplemental_defs_by_name, term)
    engineer_defs = _lookup_rows(engineer_defs_by_name, term)
    nested = blocks_by_name.get(term)
    aliases_to = aliases_by_target.get(term, [])
    alias_named = aliases_by_alias.get(term, [])
    footnotes = footnotes_by_condition.get(term, [])

    statuses = []
    if defs:
        statuses.append("definition")
    if supplemental_defs:
        statuses.append("supplemental_definition")
    if engineer_defs:
        statuses.append("engineer_definition")
    if nested and term != control_name:
        statuses.append("logic_block")
    if aliases_to or alias_named:
        statuses.append("alias")
    if footnotes:
        statuses.append("footnote")
    if term in unresolved_terms:
        statuses.append("unresolved")
    status = "resolved" if any(
        x in statuses
        for x in (
            "definition",
            "supplemental_definition",
            "engineer_definition",
            "logic_block",
            "alias",
            "footnote",
        )
    ) and term not in unresolved_terms else "missing"
    if term in unresolved_terms and status == "resolved":
        status = "needs_review"

    preview_parts = []
    if defs:
        preview_parts.append(f"definition: {_clip(defs[0].get('definition'))}")
    if supplemental_defs:
        preview_parts.append(f"added doc: {_clip(supplemental_defs[0].get('definition'))}")
    if engineer_defs:
        preview_parts.append(f"engineer note: {_clip(engineer_defs[0].get('definition'))}")
    if nested and term != control_name:
        preview_parts.append(f"logic block: {nested.get('parse_status', 'unknown')}")
    if aliases_to:
        preview_parts.append(f"aliases: {', '.join(str(a.get('alias')) for a in aliases_to[:3])}")
    if footnotes:
        preview_parts.append(f"footnotes: {', '.join(str(f.get('ref')) for f in footnotes[:3])}")

    return {
        "term": term,
        "status": status,
        "flags": statuses,
        "preview": "; ".join(preview_parts),
        "definitions": [
            {
                "name": d.get("name"),
                "definition": d.get("definition"),
                "source": _format_source(d.get("source")),
                "kind": "spec_definition",
                "match_mode": _match_mode(term, d),
            }
            for d in defs[:4]
        ]
        + [
            {
                "name": d.get("name"),
                "definition": d.get("definition"),
                "source": _format_source(d.get("source")),
                "kind": "added_file",
                "match_mode": _match_mode(term, d),
            }
            for d in supplemental_defs[:4]
        ]
        + [
            {
                "name": d.get("name"),
                "definition": d.get("definition"),
                "source": _format_source(d.get("source")),
                "kind": "engineer_note",
                "match_mode": _match_mode(term, d),
            }
            for d in engineer_defs[:4]
        ],
        "nested_logic_block": (
            {
                "name": nested.get("name"),
                "logic_id": nested.get("id"),
                "parse_status": nested.get("parse_status"),
                "expression": _clip(nested.get("raw_expression"), 220),
                "source": _format_source(nested.get("source")),
            }
            if nested and term != control_name
            else None
        ),
        "aliases": [
            {
                "alias": a.get("alias"),
                "target": a.get("target"),
                "source": _format_source(a.get("source")),
            }
            for a in (aliases_to[:4] + alias_named[:4])
        ],
        "footnotes": [
            {
                "ref": f.get("ref"),
                "definition": f.get("definition"),
                "source": _format_source(f.get("source")),
            }
            for f in footnotes[:4]
        ],
    }


def build_logic_review_items(
    logic_blocks: list[dict[str, Any]],
    two_column_tables: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    condition_definitions: list[dict[str, Any]],
    alias_map: list[dict[str, Any]],
    footnote_definitions: list[dict[str, Any]],
    engineer_definitions: list[dict[str, Any]] | None = None,
    supplemental_definitions: list[dict[str, Any]] | None = None,
    resolved_logic_blocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """One review item per control / logic block."""
    tbl_by_control = {t.get("control_name"): t for t in two_column_tables}
    blocks_by_name = {b.get("name"): b for b in logic_blocks if b.get("name")}
    defs_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in condition_definitions:
        name = str(row.get("name") or "")
        defs_by_name.setdefault(name, []).append(row)
        norm = _normalize_term(name)
        if norm and norm != name:
            defs_by_name.setdefault(norm, []).append(row)
    supplemental_defs_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in supplemental_definitions or []:
        name = str(row.get("name") or "")
        supplemental_defs_by_name.setdefault(name, []).append(row)
        norm = _normalize_term(name)
        if norm and norm != name:
            supplemental_defs_by_name.setdefault(norm, []).append(row)
    engineer_defs_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in engineer_definitions or []:
        name = str(row.get("name") or "")
        engineer_defs_by_name.setdefault(name, []).append(row)
        norm = _normalize_term(name)
        if norm and norm != name:
            engineer_defs_by_name.setdefault(norm, []).append(row)
    aliases_by_target: dict[str, list[dict[str, Any]]] = {}
    aliases_by_alias: dict[str, list[dict[str, Any]]] = {}
    for row in alias_map:
        aliases_by_target.setdefault(str(row.get("target") or ""), []).append(row)
        aliases_by_alias.setdefault(str(row.get("alias") or ""), []).append(row)
    footnotes_by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in footnote_definitions:
        footnotes_by_condition.setdefault(str(row.get("condition_name") or ""), []).append(row)
    resolved_by_id: dict[str, dict[str, Any]] = {}
    resolved_by_name: dict[str, dict[str, Any]] = {}
    for rb in resolved_logic_blocks or []:
        rid = str(rb.get("id") or "")
        rname = str(rb.get("name") or "")
        if rid:
            resolved_by_id[rid] = rb
        if rname:
            resolved_by_name[rname] = rb
    items: list[dict[str, Any]] = []

    for lb in logic_blocks:
        if lb.get("block_type") != "two_column_control" and lb.get("table_kind") == "constant":
            continue
        name = lb.get("name", "")
        tid = lb.get("id", name)
        tree = lb.get("tree") or {}
        tbl = tbl_by_control.get(name) or {}
        expression = lb.get("raw_expression") or ast_to_expression(tree)
        engineer_terms = set(engineer_defs_by_name.keys())
        supplemental_terms = set(supplemental_defs_by_name.keys())
        review_resolved_terms = engineer_terms | supplemental_terms
        unresolved_terms = {
            str(x)
            for x in lb.get("unresolved_refs") or []
            if str(x) not in review_resolved_terms and _normalize_term(str(x)) not in review_resolved_terms
        }

        block_issues = [i for i in issues if name in (i.get("affected_items") or []) or tid in (i.get("affected_items") or [])]
        block_issues.extend(lb.get("issues") or [])
        normalized_issues = []
        for issue in block_issues:
            issue_row = dict(issue)
            affected = {str(x) for x in issue_row.get("affected_items") or []}
            affected_norm = {_normalize_term(x) for x in affected}
            if issue_row.get("type") == "unresolved_condition" and (
                affected & review_resolved_terms or affected_norm & review_resolved_terms
            ):
                issue_row["resolved_in_review"] = True
                issue_row["display_severity"] = "ok"
                issue_row["resolution_note"] = "Resolved from added clarification or attached define file; keep under review until final approval."
            else:
                issue_row["resolved_in_review"] = False
                issue_row["display_severity"] = issue_row.get("severity", "warning")
            normalized_issues.append(issue_row)

        related_candidates = [
            c
            for c in candidates
            if name in str(c.get("logic_path", ""))
            or name in str(c.get("event", ""))
            or tid in str(c.get("traceability", ""))
        ]

        table_rows = []
        for r in tbl.get("rows") or []:
            table_rows.append(
                {
                    "row_no": r.get("row_no"),
                    "control": r.get("control"),
                    "raw_condition": r.get("condition_raw"),
                    "depth": r.get("indentation_level"),
                    "detected_type": r.get("detected_type"),
                    "parsed_node": r.get("parsed_hint"),
                    "source": _format_source(r.get("source")),
                    "confidence": "low" if r.get("issue_status") == "review_required" else "medium",
                    "issue": r.get("issue_status", "ok"),
                    "parser_reason": r.get("parser_reason", ""),
                }
            )

        trace_rows = [
            _trace_row(
                term,
                control_name=name,
                defs_by_name=defs_by_name,
                supplemental_defs_by_name=supplemental_defs_by_name,
                blocks_by_name=blocks_by_name,
                aliases_by_target=aliases_by_target,
                aliases_by_alias=aliases_by_alias,
                footnotes_by_condition=footnotes_by_condition,
                engineer_defs_by_name=engineer_defs_by_name,
                unresolved_terms=unresolved_terms,
            )
            for term in _collect_terms(lb, expression)
        ]

        rb = resolved_by_id.get(tid) or resolved_by_name.get(name) or {}
        gate_status = rb.get("gate_status") or lb.get("gate_status", "")
        items.append(
            {
                "logic_id": tid,
                "control_name": name,
                "gate_status": gate_status,
                "understanding_gaps": rb.get("gaps") or lb.get("understanding_gaps") or [],
                "parse_status": lb.get("parse_status", "unknown"),
                "can_generate_candidates": lb.get(
                    "can_generate_candidates", rb.get("can_generate_candidates", False)
                ),
                "expression": expression,
                "raw_expression": str(lb.get("raw_expression") or "").strip(),
                "tree_model": tree,
                "tree_lines": render_tree_lines(tree) if tree.get("type") != "empty" else [],
                "tree_nodes": flatten_ast_to_rows(tid, tree),
                "source_evidence": {
                    "file": (lb.get("source") or {}).get("file", ""),
                    "table": (lb.get("source") or {}).get("table", ""),
                    "table_id": (lb.get("source") or {}).get("table_id", ""),
                    "control": (lb.get("source") or {}).get("control", ""),
                    "summary": _format_source(lb.get("source")),
                },
                "visual_source": lb.get("visual_source")
                or {
                    "kind": "logic_table_rows",
                    "title": name,
                    "source": lb.get("source") or {},
                    "rows": [
                        {
                            "row_no": row.get("row_no"),
                            "cells": [row.get("control"), row.get("raw_condition")],
                        }
                        for row in table_rows
                    ],
                },
                "unresolved_refs": list(unresolved_terms),
                "engineer_resolved_terms": sorted(
                    {
                        str(x)
                        for x in lb.get("unresolved_refs") or []
                        if str(x) in engineer_terms or _normalize_term(str(x)) in engineer_terms
                    }
                ),
                "review_resolved_terms": sorted(
                    {
                        str(x)
                        for x in lb.get("unresolved_refs") or []
                        if str(x) in review_resolved_terms or _normalize_term(str(x)) in review_resolved_terms
                    }
                ),
                "trace_rows": trace_rows,
                "parser_notes": lb.get("parser_notes") or [],
                "issues": normalized_issues,
                "table_rows": table_rows,
                "candidates": related_candidates,
                "review_required": lb.get("parse_status") != "ok" or lb.get("review_required", True),
            }
        )
    return items
