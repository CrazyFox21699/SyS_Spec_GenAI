"""Build path × test-case coverage matrix for one logic group."""

from __future__ import annotations

from typing import Any


def _candidate_path_id(candidate: dict[str, Any]) -> str:
    trace = candidate.get("traceability") or {}
    cov = candidate.get("coverage") or {}
    return str(
        cov.get("path_id")
        or trace.get("path_id")
        or trace.get("logic_path")
        or ""
    ).strip()


def _candidate_logic_id(candidate: dict[str, Any]) -> str:
    trace = candidate.get("traceability") or {}
    cov = candidate.get("coverage") or {}
    return str(cov.get("logic_id") or trace.get("logic_block") or "").strip()


def _given_signals(candidate: dict[str, Any]) -> set[str]:
    op = candidate.get("operation") or {}
    given = op.get("given") or []
    out: set[str] = set()
    if isinstance(given, list):
        for g in given:
            if isinstance(g, dict) and g.get("signal"):
                out.add(str(g["signal"]).upper())
            elif isinstance(g, str):
                for token in g.replace(",", " ").split():
                    if token.isupper() or "_" in token:
                        out.add(token.upper())
    elif isinstance(given, str):
        for token in given.replace(",", " ").split():
            if len(token) > 2 and token[0].isalpha():
                out.add(token.upper())
    return out


def build_path_tc_matrix(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    resolved_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return rows=paths, cells=TC coverage for one logic group."""
    from src.engine.mcdc_planner import enumerate_or_paths, plan_test_paths

    logic_blocks = bundle.get("logic_blocks") or []
    resolved_all = bundle.get("resolved_logic_blocks") or []
    lb = next((b for b in logic_blocks if str(b.get("id") or "") == logic_id), None)
    rb = resolved_block or next((r for r in resolved_all if str(r.get("id") or "") == logic_id), None)
    if not lb and not rb:
        return {"ok": False, "reason": "logic_not_found", "logic_id": logic_id}

    control = str((rb or lb or {}).get("name") or logic_id)
    tree = (rb or lb or {}).get("tree") or {}
    path_specs, planner_meta = plan_test_paths(rb or lb or {}, control_name=control)
    base_paths = {str(p.get("path_id") or ""): p for p in enumerate_or_paths(tree)}

    candidates = [
        c
        for c in bundle.get("test_candidates") or []
        if _candidate_logic_id(c) == logic_id or logic_id in str(c.get("id") or "")
    ]

    paths: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []

    for ps in path_specs:
        path_id = str(ps.get("path_id") or "")
        base = base_paths.get(path_id) or {}
        path_atoms = {
            str(a.get("signal") or "").upper()
            for a in (base.get("atoms") or ps.get("atoms") or [])
            if a.get("signal")
        }
        path_given = list(ps.get("given_items") or [])
        if not path_given:
            path_given = [
                {
                    "signal": a.get("signal"),
                    "value": a.get("value") or "1",
                    "operator": a.get("operator", "=="),
                }
                for a in base.get("atoms") or []
                if a.get("signal")
            ]
        covered: list[str] = []
        partial: list[str] = []
        wrong: list[str] = []

        for cand in candidates:
            cid = str(cand.get("id") or "")
            cand_path = _candidate_path_id(cand)
            given_sigs = _given_signals(cand)

            if cand_path and path_id and cand_path == path_id:
                status = "covered"
            elif cand_path and path_id and cand_path.startswith(f"{path_id}_"):
                status = "partial"
            elif path_atoms and path_atoms.issubset(given_sigs):
                status = "covered"
            elif path_atoms and given_sigs & path_atoms:
                status = "partial"
            else:
                continue

            cell = {
                "path_id": path_id,
                "candidate_id": cid,
                "status": status,
                "candidate_path_id": cand_path,
                "review_status": cand.get("review_status"),
            }
            cells.append(cell)
            if status == "covered":
                covered.append(cid)
            elif status == "partial":
                partial.append(cid)
            else:
                wrong.append(cid)

        paths.append(
            {
                "path_id": path_id,
                "label": ps.get("label") or path_id,
                "footnote_branch": ps.get("footnote_branch"),
                "atom_count": len(path_atoms),
                "signals": sorted(path_atoms),
                "given_template": path_given,
                "covered_count": len(covered),
                "partial_count": len(partial),
                "candidate_ids": covered + partial,
                "coverage_status": (
                    "full"
                    if covered
                    else ("partial" if partial else "missing")
                ),
            }
        )

    total = len(paths)
    full = sum(1 for p in paths if p["coverage_status"] == "full")
    missing = sum(1 for p in paths if p["coverage_status"] == "missing")

    matrix = {
        "ok": True,
        "logic_id": logic_id,
        "control_name": control,
        "paths": paths,
        "cells": cells,
        "candidates": [
            {
                "id": c.get("id"),
                "path_id": _candidate_path_id(c),
                "review_status": c.get("review_status"),
                "status": c.get("status"),
            }
            for c in candidates
        ],
        "summary": {
            "path_count": total,
            "paths_full": full,
            "paths_partial": total - full - missing,
            "paths_missing": missing,
            "candidate_count": len(candidates),
        },
        "planner_meta": planner_meta,
    }
    bundle.setdefault("path_tc_matrices", {})[logic_id] = matrix
    return matrix


def enrich_candidate_coverage(bundle: dict[str, Any], logic_id: str | None = None) -> int:
    """Write coverage.path_id onto candidates from matrix match."""
    matrices = bundle.get("path_tc_matrices") or {}
    if logic_id:
        targets = {logic_id: matrices.get(logic_id) or build_path_tc_matrix(bundle, logic_id)}
    else:
        targets = {}
        for lb in bundle.get("logic_blocks") or []:
            lid = str(lb.get("id") or "")
            if lid:
                targets[lid] = matrices.get(lid) or build_path_tc_matrix(bundle, lid)

    updated = 0
    cell_index: dict[tuple[str, str], str] = {}
    for lid, matrix in targets.items():
        if not matrix.get("ok"):
            continue
        for cell in matrix.get("cells") or []:
            if cell.get("status") == "covered":
                cell_index[(lid, str(cell.get("candidate_id") or ""))] = str(cell.get("path_id") or "")

    for cand in bundle.get("test_candidates") or []:
        cid = str(cand.get("id") or "")
        lid = _candidate_logic_id(cand)
        if logic_id and lid != logic_id:
            continue
        path_id = cell_index.get((lid, cid)) or _candidate_path_id(cand)
        if not path_id:
            continue
        cov = dict(cand.get("coverage") or {})
        if cov.get("path_id") == path_id and cov.get("logic_id") == lid:
            continue
        cov["logic_id"] = lid
        cov["path_id"] = path_id
        path_row = next(
            (p for p in (targets.get(lid) or {}).get("paths") or [] if p.get("path_id") == path_id),
            None,
        )
        if path_row:
            cov["completeness"] = path_row.get("coverage_status", "unknown")
            cov["signals_asserted"] = path_row.get("signals") or []
        cand["coverage"] = cov
        trace = dict(cand.get("traceability") or {})
        trace.setdefault("path_id", path_id)
        trace.setdefault("logic_block", lid)
        cand["traceability"] = trace
        updated += 1
    return updated
