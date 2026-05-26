"""Read Word table OOXML merge metadata (gridSpan / vMerge) for geometry-aware parsing."""

from __future__ import annotations

from typing import Any

from docx.oxml.ns import qn
from docx.table import Table

from src.models.evidence_model import make_evidence_ref


def _run_is_deleted(run_element) -> bool:
    rpr = run_element.find(qn("w:rPr"))
    if rpr is not None:
        if rpr.find(qn("w:strike")) is not None or rpr.find(qn("w:dstrike")) is not None:
            return True
    parent = run_element.getparent()
    while parent is not None:
        if parent.tag in {qn("w:del"), qn("w:moveFrom")}:
            return True
        parent = parent.getparent()
    return False


def _cell_text(tc_element) -> str:
    parts: list[str] = []
    for p in tc_element.findall(".//" + qn("w:p")):
        for r in p.findall(qn("w:r")):
            if _run_is_deleted(r):
                continue
            for node in r.iter():
                if node.tag == qn("w:t") and node.text:
                    parts.append(node.text)
    return "".join(parts).strip()


def _tc_grid_span(tc_element) -> int:
    tc_pr = tc_element.find(qn("w:tcPr"))
    if tc_pr is None:
        return 1
    gs = tc_pr.find(qn("w:gridSpan"))
    if gs is not None and gs.get(qn("w:val")):
        try:
            return max(1, int(gs.get(qn("w:val"))))
        except (TypeError, ValueError):
            return 1
    return 1


def _tc_vmerge(tc_element) -> str | None:
    tc_pr = tc_element.find(qn("w:tcPr"))
    if tc_pr is None:
        return None
    vm = tc_pr.find(qn("w:vMerge"))
    if vm is None:
        return None
    val = vm.get(qn("w:val"))
    return str(val) if val else "continue"


def _expand_row_cells(tr_element) -> list[dict[str, Any]]:
    """Expand one table row into logical columns with merge metadata."""
    cells: list[dict[str, Any]] = []
    col = 0
    for tc in tr_element.findall(qn("w:tc")):
        text = _cell_text(tc)
        colspan = _tc_grid_span(tc)
        vmerge = _tc_vmerge(tc)
        for offset in range(colspan):
            cells.append(
                {
                    "text": text if offset == 0 else "",
                    "col": col + offset,
                    "colspan": colspan if offset == 0 else 0,
                    "col_origin": offset == 0,
                    "vmerge": vmerge,
                    "is_operator": text.upper() in {"AND", "OR", "NOT"},
                }
            )
        col += colspan
    return cells


def table_to_merge_aware_grid(table: Table) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """
    Build a rectangular grid from Word OOXML, propagating vertically merged anchor text.
    Falls back to python-docx row.cells text when XML walk yields empty rows.
    """
    raw_rows: list[list[dict[str, Any]]] = []
    for tr in table._tbl.findall(qn("w:tr")):
        expanded = _expand_row_cells(tr)
        if expanded:
            raw_rows.append(expanded)

    if not raw_rows:
        grid = [[c.text.strip() for c in row.cells] for row in table.rows]
        return grid, []

    max_cols = max(len(r) for r in raw_rows)
    pending_vmerge: dict[int, str] = {}
    grid: list[list[str]] = []
    merge_evidence: list[dict[str, Any]] = []

    for row_idx, row_cells in enumerate(raw_rows):
        row_text = [""] * max_cols
        for cell in row_cells:
            col = int(cell["col"])
            if col >= max_cols:
                continue
            text = str(cell.get("text") or "")
            vmerge = cell.get("vmerge")
            if vmerge == "continue" and col in pending_vmerge:
                text = pending_vmerge[col]
            elif vmerge == "restart" and text:
                pending_vmerge[col] = text
            elif vmerge is None:
                pending_vmerge.pop(col, None)
            row_text[col] = text

            if cell.get("col_origin") and int(cell.get("colspan") or 1) > 1:
                merge_evidence.append(
                    _merge_evidence(
                        table,
                        row_idx + 1,
                        col + 1,
                        row_idx + 1,
                        col + int(cell["colspan"]),
                        text,
                    )
                )
            if vmerge == "restart" and text:
                merge_evidence.append(
                    _merge_evidence(
                        table,
                        row_idx + 1,
                        col + 1,
                        row_idx + 1,
                        col + 1,
                        text,
                        note="vMerge restart",
                    )
                )
        grid.append(row_text)

    return grid, merge_evidence


def extract_table_merge_layout(table: Table) -> list[dict[str, Any]]:
    """
    Per-row merge layout from OOXML (row 0 = first table row / header).
    Each cell entry: col, text, vmerge, merge_anchor_row, branch_key.
    """
    layout: list[dict[str, Any]] = []
    pending_text: dict[int, str] = {}
    merge_anchor: dict[int, int] = {}

    for row_idx, tr in enumerate(table._tbl.findall(qn("w:tr"))):
        expanded = _expand_row_cells(tr)
        if not expanded:
            layout.append({"row_index": row_idx, "cells": []})
            continue
        cells_out: list[dict[str, Any]] = []
        for cell in expanded:
            col = int(cell["col"])
            text = str(cell.get("text") or "")
            vmerge = cell.get("vmerge")
            if vmerge == "continue" and col in pending_text:
                text = pending_text[col]
            elif text:
                pending_text[col] = text
                merge_anchor[col] = row_idx
            elif vmerge is None:
                merge_anchor[col] = row_idx
            anchor = merge_anchor.get(col, row_idx)
            cells_out.append(
                {
                    "col": col,
                    "text": text,
                    "vmerge": vmerge,
                    "merge_anchor_row": anchor,
                    "branch_key": f"c{col}:a{anchor}",
                }
            )
        layout.append({"row_index": row_idx, "cells": cells_out})
    return layout


def build_row_branch_groups(
    table: Table,
    *,
    ctrl_idx: int = 0,
    cond_indices: list[int] | None = None,
) -> dict[int, dict[str, Any]]:
    """
    Map body row index (1-based, after header) to control text and branch_group keys.
    branch_group keys are derived from vMerge anchors on condition columns.
    """
    layout = extract_table_merge_layout(table)
    if len(layout) < 2:
        return {}

    header_cells = layout[0].get("cells") or []
    if cond_indices is None:
        cond_indices = [c["col"] for c in header_cells if c["col"] > ctrl_idx]
        if not cond_indices:
            cond_indices = list(range(ctrl_idx + 1, max((c["col"] for c in header_cells), default=ctrl_idx) + 1))

    out: dict[int, dict[str, Any]] = {}
    pending_control = ""
    for body_i, row_meta in enumerate(layout[1:], start=1):
        cells_by_col = {c["col"]: c for c in row_meta.get("cells") or []}
        ctrl_cell = cells_by_col.get(ctrl_idx, {})
        ctrl_text = str(ctrl_cell.get("text") or "").strip()
        if ctrl_text:
            pending_control = ctrl_text
        elif ctrl_cell.get("vmerge") == "continue" and pending_control:
            ctrl_text = pending_control
        else:
            ctrl_text = pending_control

        cond_keys: list[str] = []
        gate_cols: list[tuple[int, str, str]] = []
        for ci in cond_indices:
            cell = cells_by_col.get(ci, {})
            if cell:
                cond_keys.append(str(cell.get("branch_key") or f"c{ci}:a{body_i}"))
            tok = str(cell.get("text") or "").strip().upper()
            if tok in {"AND", "OR", "NOT"}:
                gate_cols.append((ci, tok, str(cell.get("branch_key") or f"c{ci}:a{body_i}")))

        branch_group = f"row:{body_i}"
        if len(gate_cols) >= 2:
            branch_group = gate_cols[1][2]
        elif len(gate_cols) == 1 and len(cond_indices) > 1:
            next_ci = cond_indices[1]
            ncell = cells_by_col.get(next_ci, {})
            nt = str(ncell.get("text") or "").strip().upper()
            if nt not in {"AND", "OR", "NOT"}:
                branch_group = f"leaf:{body_i}"
            else:
                branch_group = gate_cols[0][2]
        elif cond_keys:
            branch_group = cond_keys[-1]

        inner_gate_col = gate_cols[1][0] if len(gate_cols) >= 2 else (gate_cols[0][0] if gate_cols else None)
        out[body_i] = {
            "control": ctrl_text,
            "branch_group": branch_group,
            "inner_gate_col": inner_gate_col,
            "cond_branch_keys": cond_keys,
        }
    return out


def collect_word_merged_cell_evidence(
    table: Table,
    file_name: str,
    *,
    table_id: str,
) -> list[dict[str, Any]]:
    """Collect merge evidence refs for a Word table (additive; safe when no merges)."""
    _, evidence = table_to_merge_aware_grid(table)
    if evidence:
        return evidence
    out: list[dict[str, Any]] = []
    for row_idx, tr in enumerate(table._tbl.findall(qn("w:tr")), start=1):
        col = 0
        for tc in tr.findall(qn("w:tc")):
            colspan = _tc_grid_span(tc)
            vmerge = _tc_vmerge(tc)
            text = _cell_text(tc)
            if colspan > 1 or vmerge == "restart":
                out.append(
                    _merge_evidence(
                        table,
                        row_idx,
                        col + 1,
                        row_idx,
                        col + colspan,
                        text,
                        file_name=file_name,
                        table_id=table_id,
                    )
                )
            col += colspan
    return out


def _merge_evidence(
    table: Table,
    row_start: int,
    col_start: int,
    row_end: int,
    col_end: int,
    text: str,
    *,
    file_name: str = "",
    table_id: str = "",
    note: str = "",
) -> dict[str, Any]:
    merge_range = f"R{row_start}C{col_start}:R{row_end}C{col_end}"
    locator_parts = []
    if file_name:
        locator_parts.append(file_name)
    if table_id:
        locator_parts.append(table_id)
    locator_parts.append(merge_range)
    locator = " / ".join(locator_parts)
    return make_evidence_ref(
        kind="table_merged_region",
        file=file_name or None,
        locator=locator,
        source={
            "file": file_name,
            "table": table_id,
            "merge_range": merge_range,
            "row_start": row_start,
            "row_end": row_end,
            "col_start": col_start,
            "col_end": col_end,
            "merge_note": note,
        },
        excerpt=text,
        confidence="high" if text else "low",
        review_required=not bool(text),
    )
