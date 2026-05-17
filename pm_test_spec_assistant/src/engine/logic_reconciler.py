"""Reconcile paragraph formulas with logic-table blocks; flag table inconsistencies."""

from __future__ import annotations

import re
from typing import Any


def _norm_expr(expr: str) -> str:
    return re.sub(r"\s+", " ", (expr or "").upper().strip())


def _table_row_warnings(rows: list[dict[str, Any]]) -> list[str]:
    """Detect duplicate condition IDs on AND spine with different details (common spec typo)."""
    warnings: list[str] = []
    and_seen: dict[str, str] = {}
    in_or = False
    for i, row in enumerate(rows):
        logic = (row.get("logic") or "").upper().strip()
        cond = (row.get("condition") or "").strip()
        detail = (row.get("detail") or "").strip()
        if not cond:
            continue
        if logic == "OR":
            in_or = True
            continue
        if logic == "AND":
            in_or = False
        if in_or and logic == "":
            continue
        if logic == "" and i > 0 and (rows[i - 1].get("logic") or "").upper() == "OR":
            continue
        if logic in ("AND", ""):
            if cond in and_seen and detail and and_seen[cond] != detail:
                warnings.append(
                    f"Duplicate `{cond}` on AND spine with different details "
                    f"('{and_seen[cond][:40]}' vs '{detail[:40]}') — verify condition ID (e.g. Condition_B)."
                )
            elif cond in and_seen:
                warnings.append(f"Duplicate `{cond}` repeated on AND spine.")
            and_seen[cond] = detail
    return warnings


def reconcile_logic_blocks(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Attach table_warnings; link table blocks to canonical paragraph formulas when names align.
    Returns (blocks, reconciliation_issues).
    """
    issues: list[dict[str, Any]] = []
    formulas: dict[str, dict[str, Any]] = {}
    for b in blocks:
        src = b.get("source") or {}
        if src.get("kind") == "paragraph_formula":
            formulas[b.get("name", "")] = b

    alias = {
        "SHUT_OFF": "SHUT_OFF_PERMISSION",
        "SHUTOFF": "SHUT_OFF_PERMISSION",
    }

    for b in blocks:
        rows = b.get("rows") or []
        tw = _table_row_warnings(rows)
        if tw:
            b["table_warnings"] = tw
            for w in tw:
                issues.append(
                    {
                        "severity": "warning",
                        "type": "logic_table_inconsistency",
                        "message": w,
                        "affected_items": [b.get("id", b.get("name", ""))],
                        "required_action": "Confirm condition IDs in source Word/Excel table",
                    }
                )

        src = b.get("source") or {}
        if src.get("kind") == "paragraph_formula":
            b["canonical"] = True
            continue

        name = str(b.get("name", ""))
        canon_name = alias.get(name.upper(), name)
        canon = formulas.get(canon_name)
        if not canon:
            continue

        b["canonical_ref"] = canon.get("id")
        b_expr = _norm_expr(b.get("raw_expression", ""))
        c_expr = _norm_expr(canon.get("raw_expression", ""))
        if b_expr != c_expr:
            issues.append(
                {
                    "severity": "warning",
                    "type": "logic_table_formula_mismatch",
                    "message": (
                        f"Table `{name}` expression differs from paragraph formula `{canon_name}`."
                    ),
                    "affected_items": [b.get("id", ""), canon.get("id", "")],
                    "required_action": (
                        f"Table: `{b.get('raw_expression', '')[:120]}` vs "
                        f"Formula: `{canon.get('raw_expression', '')[:120]}` — use formula if authoritative."
                    ),
                }
            )
            b["superseded_by_formula"] = canon.get("id")
        else:
            b["matches_formula"] = True

    return blocks, issues
