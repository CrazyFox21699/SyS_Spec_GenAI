"""Deep path compliance checks using the logic path simulator."""

from __future__ import annotations

from typing import Any


def _assignments_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    op = candidate.get("operation") or {}
    given = op.get("given") or []
    out: dict[str, Any] = {}
    if isinstance(given, list):
        for g in given:
            if isinstance(g, dict) and g.get("signal"):
                out[str(g["signal"])] = g.get("value", "1")
    return out


def _assignments_from_path(path_spec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in path_spec.get("given_items") or []:
        sig = str(item.get("signal") or "").strip()
        if not sig:
            continue
        val = item.get("value", "1")
        if item.get("negated"):
            val = "0"
        out[sig] = val
    return out


def analyze_path_compliance(
    path_spec: dict[str, Any],
    candidate: dict[str, Any],
    tree: dict[str, Any],
) -> dict[str, Any]:
    """Check whether candidate Given activates the intended path."""
    from src.engine.logic_path_simulator import simulate_logic_path

    path_assign = _assignments_from_path(path_spec)
    cand_assign = _assignments_from_candidate(candidate)
    merged = {**path_assign, **cand_assign}
    sim = simulate_logic_path(tree, merged)

    path_signals = {str(a.get("signal") or "").upper() for a in path_spec.get("atoms") or [] if a.get("signal")}
    cand_signals = {k.upper() for k in cand_assign.keys()}
    missing = sorted(path_signals - cand_signals)
    extra = sorted(cand_signals - path_signals)

    status = "ok"
    issues: list[str] = []
    if sim.get("status") != "active":
        status = "wrong_path"
        issues.append("Simulator did not activate control for merged Given")
    if missing:
        status = "partial" if status == "ok" else status
        issues.append(f"Missing signals: {', '.join(missing)}")
    if extra and path_signals:
        issues.append(f"Extra signals: {', '.join(extra)}")

    return {
        "status": status,
        "simulator_status": sim.get("status"),
        "active_node_ids": sim.get("active_node_ids") or [],
        "missing_signals": missing,
        "extra_signals": extra,
        "issues": issues,
    }


def analyze_matrix_compliance(matrix: dict[str, Any], tree: dict[str, Any]) -> dict[str, Any]:
    """Annotate matrix cells with compliance results."""
    paths_by_id = {str(p.get("path_id") or ""): p for p in matrix.get("paths") or []}
    enriched: list[dict[str, Any]] = []
    wrong_given = 0
    for cell in matrix.get("cells") or []:
        path_id = str(cell.get("path_id") or "")
        path_spec = paths_by_id.get(path_id) or {}
        cand = {"id": cell.get("candidate_id"), "operation": {"given": path_spec.get("given_template") or []}}
        # Load real candidate given from bundle caller if needed — here use cell metadata
        result = analyze_path_compliance(path_spec, cand, tree)
        if result.get("status") == "wrong_path":
            wrong_given += 1
        enriched.append({**cell, "compliance": result})
    return {
        "cells": enriched,
        "wrong_given_count": wrong_given,
    }
