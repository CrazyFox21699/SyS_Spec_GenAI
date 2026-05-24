"""Parse Word/Excel two-column (and multi-column nested) Control | Condition tables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

LOGIC_OPS = frozenset({"AND", "OR", "NOT"})
FOOTNOTE_RE = re.compile(r"\(\*(\d+)\)")
ALIAS_RE = re.compile(r"^alias\s+of\s+(.+)$", re.I)
CODE_DEF_RE = re.compile(r"^[a-z_][\w.]*\s*==", re.I)
TIMING_VALUE_RE = re.compile(r"(\d+)\s*\[(\w+)\](?:\s+(\d+))?")


@dataclass
class TwoColumnRow:
    row_no: int
    control: str
    condition_raw: str
    condition_cells: list[str] = field(default_factory=list)
    indentation_level: int = 0
    detected_type: str = "unknown"
    parsed_hint: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    issue_status: str = "ok"
    branch_group: str = ""
    control_kind: str = "logic_control"


@dataclass
class ParsedTwoColumnTable:
    table_id: str
    control_name: str
    rows: list[TwoColumnRow] = field(default_factory=list)
    table_kind: str = "logic"  # logic | alias | constant | definition
    source: dict[str, Any] = field(default_factory=dict)
    visual_rows: list[dict[str, Any]] = field(default_factory=list)


def _dedupe_row_cells(cells: list[str]) -> list[str]:
    out: list[str] = []
    for c in cells:
        c = (c or "").strip()
        if out and c == out[-1] and c:
            continue
        if c:
            out.append(c)
    return out


def _leading_spaces_level(text: str) -> int:
    if not text:
        return 0
    spaces = len(text) - len(text.lstrip(" "))
    return spaces // 2 if spaces else (len(text) - len(text.lstrip("\t"))) // 2


def _classify_token(token: str) -> str:
    t = token.strip()
    upper = t.upper()
    if upper in LOGIC_OPS:
        return f"logic_gate_{upper}"
    if FOOTNOTE_RE.search(t):
        return "condition_reference"
    if ALIAS_RE.search(t):
        return "alias_mapping"
    if CODE_DEF_RE.search(t):
        return "code_definition"
    if TIMING_VALUE_RE.search(t) or re.search(r"\[\s*ms\s*\]", t, re.I):
        return "timing_constant"
    if re.match(r"^[A-Z][A-Z0-9_]+$", t):
        return "condition_reference"
    if re.match(r"^[a-z][a-z0-9_]*$", t):
        return "word_definition"
    if upper.startswith("NOT "):
        return "logic_gate_NOT"
    return "unknown"


def _normalize_grid(grid: list[list[str]]) -> list[list[str]]:
    return [[(c or "").strip() for c in row] for row in grid if any((c or "").strip() for c in row)]


def detect_table_kind(header: list[str], body: list[list[str]]) -> str:
    hdr = " ".join(header).lower()
    if "alias" in hdr or any("alias of" in " ".join(r).lower() for r in body[:8]):
        return "alias"
    if "value" in hdr and any(
        TIMING_VALUE_RE.search(r[-1] if r else "") for r in body[:12] if len(r) > 1
    ):
        return "constant"
    if header and header[0].lower() in ("control", "item") and "condition" in hdr:
        return "logic"
    return "logic"


def parse_control_condition_grid(
    grid: list[list[str]],
    source: dict[str, Any],
    *,
    table_id: str = "T01",
    merge_branch_by_row: dict[int, dict[str, Any]] | None = None,
) -> list[ParsedTwoColumnTable]:
    """Parse one Word/Excel grid into one or more control-group tables."""
    grid = _normalize_grid(grid)
    if len(grid) < 2:
        return []

    header = [c.lower() for c in grid[0]]
    body = grid[1:]
    kind = detect_table_kind(grid[0], body)

    # Find control column and condition column(s)
    ctrl_idx = 0
    cond_indices = [i for i, h in enumerate(header) if "condition" in h or h == "cond"]
    if not cond_indices:
        cond_indices = list(range(1, len(header)))

    if kind == "alias":
        return [_parse_alias_table(body, source, table_id)]

    if kind == "constant":
        return [_parse_constant_table(body, source, table_id)]

    return _parse_nested_logic_tables(
        body, ctrl_idx, cond_indices, source, table_id, merge_branch_by_row=merge_branch_by_row
    )


def _parse_alias_table(
    body: list[list[str]], source: dict[str, Any], table_id: str
) -> ParsedTwoColumnTable:
    rows: list[TwoColumnRow] = []
    for ri, cells in enumerate(body, start=2):
        cells = _dedupe_row_cells(cells)
        if len(cells) < 2:
            continue
        alias, target = cells[0], cells[1]
        m = ALIAS_RE.search(target)
        parsed = m.group(1).strip() if m else target
        rows.append(
            TwoColumnRow(
                row_no=ri,
                control=alias,
                condition_raw=target,
                detected_type="alias_mapping",
                parsed_hint=parsed,
                source={**source, "row": ri},
            )
        )
    return ParsedTwoColumnTable(
        table_id=table_id,
        control_name="ALIAS_MAP",
        rows=rows,
        table_kind="alias",
        source=source,
    )


def _parse_constant_table(
    body: list[list[str]], source: dict[str, Any], table_id: str
) -> ParsedTwoColumnTable:
    rows: list[TwoColumnRow] = []
    for ri, cells in enumerate(body, start=2):
        cells = _dedupe_row_cells(cells)
        if len(cells) < 2:
            continue
        name = cells[0]
        desc = cells[1] if len(cells) > 2 else ""
        val = cells[-1] if len(cells) >= 3 else (cells[1] if len(cells) == 2 else "")
        m = TIMING_VALUE_RE.search(val)
        hint = val
        dtype = "timing_constant"
        status = "ok"
        if m:
            value, unit, tolerance = m.group(1), m.group(2), m.group(3)
            if tolerance:
                hint = f"value={value} unit={unit} tolerance=±{tolerance}"
            else:
                hint = f"value={value} unit={unit}"
        elif val.strip():
            status = "review_required"
        rows.append(
            TwoColumnRow(
                row_no=ri,
                control=name,
                condition_raw=f"{desc} | {val}".strip(" |"),
                detected_type=dtype,
                parsed_hint=hint,
                source={**source, "row": ri},
                issue_status=status,
            )
        )
    return ParsedTwoColumnTable(
        table_id=table_id,
        control_name="CONSTANTS",
        rows=rows,
        table_kind="constant",
        source=source,
    )


def _parse_nested_logic_tables(
    body: list[list[str]],
    ctrl_idx: int,
    cond_indices: list[int],
    source: dict[str, Any],
    table_id: str,
    *,
    merge_branch_by_row: dict[int, dict[str, Any]] | None = None,
) -> list[ParsedTwoColumnTable]:
    """Multi-column Condition columns represent nesting depth (common in Word merges)."""
    from src.engine.control_cell_classifier import classify_control_cell

    by_control: dict[str, list[list[str]]] = {}
    branch_by_control: dict[str, list[str]] = {}
    control_meta_by_control: dict[str, dict[str, Any]] = {}
    visual_by_control: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    current_control = ""

    for ri, cells in enumerate(body, start=2):
        merge_meta = (merge_branch_by_row or {}).get(ri, {})
        cells = _dedupe_row_cells(cells)
        while len(cells) <= max([ctrl_idx] + cond_indices):
            cells.append("")
        ctrl = cells[ctrl_idx] if ctrl_idx < len(cells) else ""
        if not ctrl and merge_meta.get("control"):
            ctrl = str(merge_meta["control"])
        if not ctrl and current_control:
            ctrl = current_control
        if not ctrl:
            continue
        current_control = ctrl
        ctrl_kind = classify_control_cell(ctrl)
        if ctrl_kind == "lifecycle":
            continue
        visual_cells = [c for c in cells if c]
        if ctrl not in visual_by_control:
            visual_by_control[ctrl] = []
        visual_by_control[ctrl].append(
            {
                "row_no": ri,
                "cells": visual_cells,
                "branch_group": str(merge_meta.get("branch_group") or f"row:{ri}"),
            }
        )
        path: list[str] = []
        if len(cond_indices) == 1 and cond_indices[0] < len(cells):
            raw = cells[cond_indices[0]]
            level = _leading_spaces_level(raw)
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    path.append(line)
            if not path and raw.strip():
                path = [raw.strip()]
        else:
            for ci in cond_indices:
                if ci < len(cells) and cells[ci].strip():
                    path.append(cells[ci].strip())

        if not path:
            continue
        if ctrl not in by_control:
            by_control[ctrl] = []
            branch_by_control[ctrl] = []
            order.append(ctrl)
            if ctrl_kind == "transition_outcome":
                control_meta_by_control[ctrl] = classify_control_cell(ctrl, as_meta=True) or {}
        by_control[ctrl].append(path)
        branch_by_control[ctrl].append(str(merge_meta.get("branch_group") or f"row:{ri}"))

    tables: list[ParsedTwoColumnTable] = []
    for i, ctrl in enumerate(order):
        paths = by_control[ctrl]
        branch_groups = branch_by_control.get(ctrl, [])
        ctrl_meta = control_meta_by_control.get(ctrl, {})
        rows: list[TwoColumnRow] = []
        for pi, path in enumerate(paths):
            raw = " / ".join(path)
            depth = len(path) - 1
            leaf = path[-1] if path else ""
            dtype = _classify_token(leaf)
            for tok in path:
                if _classify_token(tok).startswith("logic_gate"):
                    dtype = _classify_token(tok)
                    break
            rows.append(
                TwoColumnRow(
                    row_no=pi + 2,
                    control=ctrl,
                    condition_raw=raw,
                    condition_cells=path,
                    indentation_level=depth,
                    detected_type=dtype,
                    parsed_hint=" -> ".join(path),
                    source={**source, "path_index": pi},
                    branch_group=branch_groups[pi] if pi < len(branch_groups) else "",
                    control_kind=ctrl_meta.get("kind", "logic_control"),
                )
            )
        tables.append(
            ParsedTwoColumnTable(
                table_id=f"{table_id}_{i+1:02d}",
                control_name=ctrl,
                rows=rows,
                table_kind="logic",
                source={**source, **ctrl_meta},
                visual_rows=visual_by_control.get(ctrl, []),
            )
        )
    return tables


def tables_to_dicts(tables: list[ParsedTwoColumnTable]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tables:
        out.append(
            {
                "table_id": t.table_id,
                "control_name": t.control_name,
                "table_kind": t.table_kind,
                "source": t.source,
                "visual_rows": t.visual_rows,
                "rows": [
                    {
                        "row_no": r.row_no,
                        "control": r.control,
                        "condition_raw": r.condition_raw,
                        "condition_cells": r.condition_cells,
                        "indentation_level": r.indentation_level,
                        "detected_type": r.detected_type,
                        "parsed_hint": r.parsed_hint,
                        "issue_status": r.issue_status,
                        "source": r.source,
                        "branch_group": r.branch_group,
                        "control_kind": r.control_kind,
                    }
                    for r in t.rows
                ],
            }
        )
    return out
