"""Parse Excel/Word tables with Logic + Condition columns (merged-cell carry-forward)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.engine.condition_tree_builder import parse_condition_tree

LOGIC_OPS = frozenset({"AND", "OR", "NOT"})
CONDITION_RE = re.compile(r"^Condition_[A-Za-z0-9_]+$", re.I)
FORMULA_RE = re.compile(
    r"([A-Z][A-Z0-9_]*)\s*=\s*(.+?)(?:\s*$|\s*Judgment|\s*The\s)",
    re.I | re.M,
)
INLINE_LOGIC_RE = re.compile(
    r"([A-Z][A-Z0-9_]+)\s*=\s*((?:Condition_[A-Za-z0-9_]+\s+(?:AND|OR)\s*)+(?:\([^)]+\)|Condition_[A-Za-z0-9_]+)(?:\s+AND\s+(?:\([^)]+\)|Condition_[A-Za-z0-9_]+))*)",
    re.I,
)


@dataclass
class LogicTableRow:
    control: str = ""
    logic: str = ""
    condition: str = ""
    detail: str = ""
    source_row: int = 0


@dataclass
class LogicBlock:
    id: str
    name: str
    raw_expression: str
    tree: dict[str, Any]
    rows: list[LogicTableRow] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)
    block_type: str = "permission"  # permission | transition | reset | other
    parse_status: str = "ok"
    review_required: bool = True


def _norm_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_")


def detect_logic_table_headers(header_cells: list[str]) -> dict[str, Any] | None:
    """Map column indices for control/logic/condition/detail tables."""
    hdr = [_norm_header(c) for c in header_cells]
    if not hdr:
        return None
    idx: dict[str, Any] = {}
    for i, h in enumerate(hdr):
        if not h:
            continue
        if h in ("control", "item", "transition", "function", "event"):
            idx.setdefault("control", i)
        elif h == "logic":
            idx["logic"] = i
        elif h in ("condition", "cond"):
            idx.setdefault("condition", i)
            idx.setdefault("condition_indices", []).append(i)
        elif h in ("detail", "description", "remark", "notes"):
            idx.setdefault("detail", i)
    if "condition" in idx and ("logic" in idx or "control" in idx):
        return idx
    return None


def _dedupe_merged_row_cells(cells: list[str], *, preserve_layout: bool = False) -> list[str]:
    """Word returns repeated text for merged cells; keep first of consecutive duplicates."""
    if preserve_layout:
        out: list[str] = []
        prev = ""
        for c in cells:
            c = (c or "").strip()
            if c and c == prev:
                out.append("")
            else:
                out.append(c)
            if c:
                prev = c
        return out
    out: list[str] = []
    for c in cells:
        c = (c or "").strip()
        if out and c == out[-1] and c:
            continue
        out.append(c)
    return out


def rows_from_grid(
    grid: list[list[str]],
    source: dict[str, Any],
    *,
    block_id_prefix: str = "LB",
    row_numbers: list[int] | None = None,
    preserve_layout: bool = False,
) -> list[LogicBlock]:
    """Parse one sheet/table grid into logic blocks grouped by control column."""
    if len(grid) < 2:
        return []
    colmap = detect_logic_table_headers(grid[0])
    if not colmap:
        return []

    data_rows: list[LogicTableRow] = []
    current_control = ""
    condition_indices = colmap.get("condition_indices") or [colmap["condition"]]
    first_condition_idx = min(condition_indices)
    max_col_idx = max(
        value for value in colmap.values() if isinstance(value, int)
    )
    for offset, raw_cells in enumerate(grid[1:], start=1):
        ri = row_numbers[offset] if row_numbers and offset < len(row_numbers) else offset + 1
        cells = _dedupe_merged_row_cells(raw_cells, preserve_layout=preserve_layout)
        while len(cells) <= max_col_idx:
            cells.append("")

        ctrl = cells[colmap["control"]] if "control" in colmap else ""
        if ctrl:
            current_control = ctrl
        if "logic" in colmap:
            logic = cells[colmap["logic"]].upper()
        else:
            inferred_logic = [
                (cells[idx] or "").strip().upper()
                for idx in range(colmap.get("control", 0) + 1, first_condition_idx)
                if (cells[idx] or "").strip().upper() in LOGIC_OPS
            ]
            logic = inferred_logic[-1] if inferred_logic else ""
        cond_parts: list[str] = []
        for idx in range(first_condition_idx, len(cells)):
            text = (cells[idx] or "").strip()
            if not text:
                continue
            if cond_parts and text == cond_parts[-1]:
                continue
            cond_parts.append(text)
        cond = " / ".join(cond_parts)
        detail = cells[colmap["detail"]] if "detail" in colmap else ""

        if not cond and not logic and not detail:
            continue
        if not cond and not logic:
            continue

        data_rows.append(
            LogicTableRow(
                control=current_control,
                logic=logic,
                condition=cond,
                detail=detail,
                source_row=ri,
            )
        )

    return _group_rows_into_blocks(data_rows, source, block_id_prefix)


def _group_rows_into_blocks(
    data_rows: list[LogicTableRow],
    source: dict[str, Any],
    prefix: str,
) -> list[LogicBlock]:
    """Group consecutive rows by control name into one logic block each."""
    if not data_rows:
        return []

    blocks: list[LogicBlock] = []
    by_control: dict[str, list[LogicTableRow]] = {}
    order: list[str] = []
    for row in data_rows:
        key = row.control or "_default"
        if key not in by_control:
            by_control[key] = []
            order.append(key)
        by_control[key].append(row)

    for bi, ctrl in enumerate(order):
        rows = by_control[ctrl]
        expr = _rows_to_expression(rows)
        tree = parse_condition_tree(expr)
        btype = _infer_block_type(ctrl, expr)
        blocks.append(
            LogicBlock(
                id=f"{prefix}_{bi+1:03d}",
                name=ctrl if ctrl != "_default" else f"logic_block_{bi+1}",
                raw_expression=expr,
                tree=tree,
                rows=rows,
                source={**source, "control": ctrl, "row_span": [r.source_row for r in rows]},
                block_type=btype,
                parse_status=tree.get("parse_status", "partial"),
                review_required=True,
            )
        )
    return blocks


def _rows_to_expression(rows: list[LogicTableRow]) -> str:
    """
    Build boolean expression from logic table rows.
    Handles: AND spine; OR runs; final row with empty logic but condition (OR tail).
    """
    and_parts: list[str] = []
    or_buf: list[str] = []

    def flush_or() -> None:
        nonlocal or_buf
        if or_buf:
            if len(or_buf) == 1:
                and_parts.append(or_buf[0])
            else:
                and_parts.append("(" + " OR ".join(or_buf) + ")")
            or_buf = []

    for i, row in enumerate(rows):
        logic = (row.logic or "").upper().strip()
        cond = (row.condition or "").strip()
        if not cond:
            continue

        if logic == "OR":
            or_buf.append(cond)
        elif logic == "AND":
            flush_or()
            and_parts.append(cond)
        elif logic == "NOT":
            flush_or()
            and_parts.append(f"NOT {cond}")
        elif logic == "":
            # Merged tail: often last OR operand (Condition_D with no operator cell)
            if or_buf:
                or_buf.append(cond)
            elif i > 0 and (rows[i - 1].logic or "").upper() == "OR":
                or_buf.append(cond)
            else:
                flush_or()
                and_parts.append(cond)
        else:
            flush_or()
            if cond:
                and_parts.append(cond)

    flush_or()
    if not and_parts:
        return " | ".join(r.condition for r in rows if r.condition)
    return " AND ".join(and_parts)


def _infer_block_type(control: str, expr: str) -> str:
    c = control.upper()
    if "RESET" in c:
        return "reset"
    if "→" in control or "->" in control or "TRANSITION" in c:
        return "transition"
    if "SHUT" in c or "PERMISSION" in c or "PERM" in c:
        return "permission"
    if " OR " in expr.upper() and " AND " not in expr.upper():
        return "reset"
    return "other"


def extract_formulas_from_text(text: str, source: dict[str, Any]) -> list[LogicBlock]:
    """Extract SHUT_OFF_PERMISSION = ... style formulas from paragraphs."""
    blocks: list[LogicBlock] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(
            r"^([A-Z][A-Z0-9_]+)\s*=\s*(.+)$",
            line,
        )
        if not m or "Condition_" not in line:
            continue
        name = m.group(1).strip()
        expr = m.group(2).strip()
        if len(expr) > 500:
            expr = expr[:500]
        tree = parse_condition_tree(expr)
        blocks.append(
            LogicBlock(
                id=f"FORMULA_{len(blocks)+1:03d}",
                name=name,
                raw_expression=expr,
                tree=tree,
                rows=[],
                source={**source, "kind": "paragraph_formula"},
                block_type=_infer_block_type(name, expr),
                parse_status=tree.get("parse_status", "partial"),
                review_required=True,
            )
        )
    return blocks


def parse_transition_table(
    grid: list[list[str]],
    source: dict[str, Any],
    *,
    row_numbers: list[int] | None = None,
    preserve_layout: bool = False,
) -> list[dict[str, Any]]:
    """Parse state transition tables (Previous State / Next State / NORMAL → SHUT_OFF)."""
    if len(grid) < 2:
        return []
    hdr = [_norm_header(c) for c in grid[0]]
    transitions: list[dict[str, Any]] = []
    previous_idx = next((idx for idx, token in enumerate(hdr) if "previous" in token), None)
    next_idx = next((idx for idx, token in enumerate(hdr) if "next" in token), None)
    output_idx = next((idx for idx, token in enumerate(hdr) if "output" in token), None)

    if previous_idx is not None and next_idx is not None:
        for offset, cells in enumerate(grid[1:], start=1):
            ri = row_numbers[offset] if row_numbers and offset < len(row_numbers) else offset + 1
            cells = _dedupe_merged_row_cells(cells, preserve_layout=preserve_layout)
            if previous_idx >= len(cells) or next_idx >= len(cells):
                continue
            from_state = (cells[previous_idx] or "").strip()
            to_state = (cells[next_idx] or "").strip()
            if not from_state and not to_state:
                continue
            raw_condition = " | ".join(part for part in cells if part)
            row: dict[str, Any] = {
                "id": f"SM_{len(transitions)+1:03d}",
                "from_state": from_state.upper() if from_state else None,
                "to_state": to_state.upper() if to_state else None,
                "event": "state_transition",
                "raw_condition": raw_condition,
                "source": {**source, "row": ri},
                "confidence": "medium",
                "review_required": True,
            }
            if output_idx is not None and output_idx < len(cells) and cells[output_idx]:
                row["outputs"] = [cells[output_idx]]
            transitions.append(row)
        if transitions:
            return transitions

    # Pattern: row with arrow in first column
    for offset, cells in enumerate(grid[1:], start=1):
        ri = row_numbers[offset] if row_numbers and offset < len(row_numbers) else offset + 1
        cells = _dedupe_merged_row_cells(cells, preserve_layout=preserve_layout)
        if not any(cells):
            continue
        joined = " ".join(cells)
        arrow_m = re.search(r"(\w+)\s*(?:→|->)\s*(\w+)", joined, re.I)
        if arrow_m:
            transitions.append(
                {
                    "id": f"SM_{len(transitions)+1:03d}",
                    "from_state": arrow_m.group(1).upper(),
                    "to_state": arrow_m.group(2).upper(),
                    "event": None,
                    "raw_condition": joined,
                    "source": {**source, "row": ri},
                    "confidence": "medium",
                    "review_required": True,
                }
            )
            continue
        # Item / Expected Value table (e.g. Previous State | NORMAL)
        item_idx = 0
        val_idx = 1 if len(cells) > 1 else 0
        item = cells[item_idx].lower() if item_idx < len(cells) else ""
        val = cells[val_idx] if val_idx < len(cells) else ""
        if "previous" in item and val:
            transitions.append(
                {
                    "id": f"SM_{len(transitions)+1:03d}",
                    "from_state": val.upper(),
                    "to_state": None,
                    "event": "state_transition",
                    "raw_condition": f"Previous State = {val}",
                    "source": {**source, "row": ri},
                    "confidence": "medium",
                    "review_required": True,
                }
            )
        elif "next" in item and val:
            if transitions and transitions[-1].get("to_state") is None:
                transitions[-1]["to_state"] = val.upper()
                transitions[-1]["raw_condition"] += f"; Next State = {val}"
            else:
                transitions.append(
                    {
                        "id": f"SM_{len(transitions)+1:03d}",
                        "from_state": None,
                        "to_state": val.upper(),
                        "event": "state_transition",
                        "raw_condition": f"Next State = {val}",
                        "source": {**source, "row": ri},
                        "confidence": "medium",
                        "review_required": True,
                    }
                )
        elif "output" in item and val and transitions:
            transitions[-1].setdefault("outputs", []).append(val)
    return transitions


def transitions_from_logic_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn logic blocks named NORMAL → SHUT_OFF into state-machine transitions."""
    out: list[dict[str, Any]] = []
    for b in blocks:
        name = str(b.get("name", ""))
        m = re.search(r"(\w+)\s*(?:→|->)\s*(\w+)", name, re.I)
        if not m:
            continue
        out.append(
            {
                "id": f"SM_LB_{len(out)+1:03d}",
                "from_state": m.group(1).upper(),
                "to_state": m.group(2).upper(),
                "event": "logic_table_transition",
                "raw_condition": b.get("raw_expression", ""),
                "condition_tree": b.get("tree"),
                "source": b.get("source"),
                "confidence": "medium",
                "review_required": True,
            }
        )
    return out
