"""Two-column table logic blocks — delegates to generic indentation AST parser."""

from __future__ import annotations

import re
from typing import Any

from src.engine.indentation_ast_parser import (
    ast_to_expression,
    paths_to_ast,
)
from src.engine.logic_atom import enrich_table_ast_with_atoms
from src.parsers.two_column_table_parser import FOOTNOTE_RE, ParsedTwoColumnTable

LOGIC_OPS = frozenset({"AND", "OR", "NOT"})


def parse_table_to_logic_block(table: ParsedTwoColumnTable) -> dict[str, Any]:
    paths = [r.condition_cells or [r.condition_raw] for r in table.rows]
    branch_groups = [str(r.branch_group or "") for r in table.rows]
    source = {**table.source, "control": table.control_name, "table_id": table.table_id}
    ast, parser_notes = paths_to_ast(
        paths,
        source,
        branch_groups=branch_groups if any(branch_groups) else None,
    )
    expr = ast_to_expression(ast)
    ast = enrich_table_ast_with_atoms(ast)
    issues: list[dict[str, Any]] = []

    for note in parser_notes:
        issues.append(
            {
                "type": note.get("type", "parser_note"),
                "message": note.get("message", ""),
                "severity": note.get("severity", "info"),
                "parser_reason": note.get("parser_reason", ""),
            }
        )

    parse_status = ast.get("parse_status", "ok" if expr else "failed")
    from src.engine.condition_tree_builder import aggregate_tree_parse_status

    tree_status = aggregate_tree_parse_status(ast)
    if tree_status == "partial" and parse_status == "ok":
        parse_status = "partial"
    elif tree_status == "failed":
        parse_status = "failed"
    if ast.get("type") == "empty" or not expr:
        parse_status = "failed"
        issues.append(
            {
                "type": "condition_parse_failed",
                "message": f"Could not build logic tree for control `{table.control_name}`",
                "severity": "error",
                "parser_reason": "No valid expression could be derived from table rows.",
            }
        )
    if parse_status == "partial":
        issues.append(
            {
                "type": "unsupported_logic_format",
                "message": f"Partial or ambiguous structure for `{table.control_name}` — engineer review required",
                "severity": "error",
                "parser_reason": ast.get("parser_reason", "Ambiguous row grouping"),
            }
        )

    outcome = table.source.get("outcome_label") or table.source.get("label")
    block_name = table.control_name
    if table.source.get("kind") == "transition_outcome" and outcome:
        block_name = str(outcome)

    return {
        "id": f"TC2_{table.table_id}",
        "name": block_name,
        "control_name": table.control_name,
        "outcome_label": outcome or "",
        "from_state": table.source.get("from_state", ""),
        "to_state": table.source.get("to_state", ""),
        "control_kind": table.rows[0].control_kind if table.rows else "logic_control",
        "raw_expression": expr,
        "tree": ast,
        "block_type": "two_column_control",
        "parse_status": parse_status,
        "review_required": parse_status != "ok",
        "can_generate_candidates": parse_status == "ok",
        "source": source,
        "table_kind": table.table_kind,
        "row_paths": paths,
        "visual_source": {
            "kind": "logic_table",
            "title": table.control_name,
            "source": source,
            "rows": table.visual_rows,
        },
        "issues": issues,
        "parser_notes": parser_notes,
    }


def _condition_name_at_footnote(raw: str, footnote_num: str) -> str:
    mark = f"(*{footnote_num})"
    for seg in re.split(r"\s*/\s*", raw):
        if mark not in seg:
            continue
        clean = FOOTNOTE_RE.sub("", seg).strip()
        clean = re.sub(r"^NOT\s+", "", clean, flags=re.I).strip()
        m = re.match(r"^([A-Z][A-Z0-9_]+)", clean)
        if m and m.group(1).upper() not in LOGIC_OPS:
            return m.group(1)
    for seg in reversed(re.split(r"\s*/\s*", raw)):
        clean = FOOTNOTE_RE.sub("", seg).strip()
        clean = re.sub(r"^NOT\s+", "", clean, flags=re.I).strip()
        m = re.match(r"^([A-Z][A-Z0-9_]+)", clean)
        if m and m.group(1).upper() not in LOGIC_OPS:
            return m.group(1)
    return ""


def extract_footnote_refs(tables: list[ParsedTwoColumnTable]) -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tbl in tables:
        for row in tbl.rows:
            for m in FOOTNOTE_RE.finditer(row.condition_raw):
                fn = m.group(1)
                key = f"(*{fn})"
                cond_name = _condition_name_at_footnote(row.condition_raw, fn)
                dedupe_key = f"{tbl.table_id}|{row.control}|{key}|{cond_name}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                defs.append(
                    {
                        "ref": key,
                        "footnote_num": fn,
                        "condition_name": cond_name,
                        "logic_id": f"TC2_{tbl.table_id}",
                        "raw_text": row.condition_raw,
                        "control": row.control,
                        "source": row.source,
                        "definition": None,
                        "review_required": True,
                        "parser_reason": (
                            f"Footnote marker {key} found in condition row"
                            + (f" for `{cond_name}`." if cond_name else ".")
                        ),
                    }
                )
    return defs


def build_alias_map(tables: list[ParsedTwoColumnTable]) -> list[dict[str, Any]]:
    aliases: list[dict[str, Any]] = []
    for tbl in tables:
        if tbl.table_kind != "alias":
            continue
        for row in tbl.rows:
            aliases.append(
                {
                    "alias": row.control,
                    "target": row.parsed_hint or row.condition_raw,
                    "raw_text": row.condition_raw,
                    "source": row.source,
                    "review_required": False,
                    "parser_reason": "Parsed from alias mapping table row.",
                }
            )
    return aliases


def collect_condition_names(ast: dict[str, Any]) -> list[str]:
    names: list[str] = []

    def walk(n: dict[str, Any]) -> None:
        if n.get("type") == "condition":
            nm = str(n.get("name", "")).strip()
            if nm:
                names.append(nm)
        for ch in n.get("children") or []:
            walk(ch)

    walk(ast)
    return names
