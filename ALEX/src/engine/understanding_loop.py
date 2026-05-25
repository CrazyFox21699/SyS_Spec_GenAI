"""Re-run understanding gate and review artifacts after engineer/AI acceptance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.engine.logic_atom import enrich_tree_with_atoms
from src.engine.logic_review_builder import _normalize_term, build_logic_review_items
from src.engine.spec_understanding_report import build_spec_understanding_report
from src.engine.structured_overlay import accepted_constraints, get_overlay
from src.engine.footnote_materializer import link_footnotes_to_logic_blocks, materialize_footnote_attachments
from src.engine.path_tc_matrix import build_path_tc_matrix, enrich_candidate_coverage
from src.engine.understanding_gate import build_resolved_logic_blocks


def _engineer_definition_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    defs = ai.get("engineer_definitions") or {}
    rows: list[dict[str, Any]] = []
    for name, meta in defs.items():
        if not isinstance(meta, dict):
            continue
        rows.append(
            {
                "name": str(name),
                "definition": meta.get("definition", ""),
                "logic_id": str(meta.get("logic_id") or ""),
                "source": {
                    "file": "engineer_clarification",
                    "table": meta.get("logic_id", ""),
                    "row": None,
                },
            }
        )
    return rows


def _supplemental_definition_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    grouped = ai.get("supplemental_definitions") or {}
    rows: list[dict[str, Any]] = []
    for defs in grouped.values():
        for row in defs or []:
            if isinstance(row, dict):
                rows.append(dict(row))
    return rows


def collect_known_terms_for_block(bundle: dict[str, Any], logic_id: str, logic_name: str = "") -> set[str]:
    """Merge spec, engineer, supplemental, and accepted constraint signals for one control."""
    known: set[str] = set()
    for row in bundle.get("condition_definitions") or []:
        name = str(row.get("name") or "").strip()
        if name:
            known.add(name)
            known.add(_normalize_term(name))
    for row in _engineer_definition_rows(bundle):
        name = str(row.get("name") or "").strip()
        scoped = str(row.get("logic_id") or "").strip()
        if not name:
            continue
        if scoped and scoped not in (logic_id, logic_name):
            continue
        known.add(name)
        known.add(_normalize_term(name))
    for row in _supplemental_definition_rows(bundle):
        src = row.get("source") or {}
        scoped = str(src.get("table") or src.get("logic_id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        if scoped and scoped not in (logic_id, logic_name):
            continue
        known.add(name)
        known.add(_normalize_term(name))
    for constraint in accepted_constraints(get_overlay(bundle, logic_id)):
        sig = str(constraint.get("signal") or "").strip()
        if sig:
            known.add(sig)
            known.add(_normalize_term(sig))
    for row in bundle.get("alias_map") or []:
        for key in ("alias", "target"):
            val = str(row.get(key) or "").strip()
            if val:
                known.add(val)
                known.add(_normalize_term(val))
    return known


def _refresh_block_unresolved_refs(logic_block: dict[str, Any], known: set[str]) -> list[str]:
    before = list(logic_block.get("unresolved_refs") or [])
    after: list[str] = []
    for ref in before:
        text = str(ref or "").strip()
        if not text:
            continue
        if text in known or _normalize_term(text) in known:
            continue
        after.append(text)
    logic_block["unresolved_refs"] = after
    return before


def rebuild_understanding(
    bundle: dict[str, Any],
    *,
    logic_ids: list[str] | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    """
    Re-evaluate understanding gate, resolved blocks, review items, and spec %.

    Mutates bundle in place. When logic_ids is set, only those blocks get gate refresh
    but logic_review_items and spec_understanding are always rebuilt globally.
    """
    logic_blocks = bundle.get("logic_blocks") or []
    if not logic_blocks:
        return {"ok": False, "reason": "no_logic_blocks", "trigger": trigger}

    target_ids = {str(x) for x in logic_ids} if logic_ids else None
    known_by_id: dict[str, set[str]] = {}
    refreshed: list[str] = []
    unresolved_cleared = 0

    for lb in logic_blocks:
        lid = str(lb.get("id") or lb.get("name") or "")
        lname = str(lb.get("name") or "")
        if target_ids is not None and lid not in target_ids and lname not in target_ids:
            continue
        known = collect_known_terms_for_block(bundle, lid, lname)
        known_by_id[lid or lname] = known
        before = _refresh_block_unresolved_refs(lb, known)
        unresolved_cleared += max(0, len(before) - len(lb.get("unresolved_refs") or []))
        tree = lb.get("tree") or {}
        if tree and tree.get("type") != "empty":
            lb["tree"] = enrich_tree_with_atoms(dict(tree))
        refreshed.append(lid or lname)

    footnotes = bundle.get("footnote_definitions") or []
    condition_defs = list(bundle.get("condition_definitions") or [])
    engineer_rows = _engineer_definition_rows(bundle)
    supplemental_rows = _supplemental_definition_rows(bundle)
    merged_condition_defs = condition_defs + [
        {"name": r["name"], "definition": r.get("definition", ""), "source": r.get("source")}
        for r in engineer_rows + supplemental_rows
        if r.get("name")
    ]

    resolved_all = build_resolved_logic_blocks(
        logic_blocks,
        footnote_definitions=footnotes,
        condition_definitions=merged_condition_defs,
        alias_map=bundle.get("alias_map") or [],
        known_by_block_id=known_by_id if known_by_id else None,
    )
    resolved_by_id = {str(r.get("id") or ""): r for r in resolved_all if r.get("id")}
    resolved_by_name = {str(r.get("name") or ""): r for r in resolved_all if r.get("name")}

    for lb in logic_blocks:
        lid = str(lb.get("id") or "")
        lname = str(lb.get("name") or "")
        if target_ids is not None and lid not in target_ids and lname not in target_ids:
            continue
        rb = resolved_by_id.get(lid) or resolved_by_name.get(lname) or {}
        if not rb:
            continue
        lb["gate_status"] = rb.get("gate_status")
        lb["can_generate_candidates"] = rb.get("can_generate_candidates", False)
        lb["understanding_gaps"] = rb.get("gaps", [])
        if rb.get("gate_status") == "ready" and lb.get("parse_status") == "ok":
            lb["review_required"] = False

    bundle["resolved_logic_blocks"] = resolved_all

    link_footnotes_to_logic_blocks(bundle)
    mat_result = materialize_footnote_attachments(
        bundle,
        logic_ids=list(target_ids) if target_ids else None,
    )

    matrix_ids = refreshed if refreshed else [str(lb.get("id") or "") for lb in logic_blocks if lb.get("id")]
    for lid in matrix_ids:
        if lid:
            build_path_tc_matrix(bundle, lid)
    enrich_candidate_coverage(bundle, logic_id=logic_ids[0] if logic_ids and len(logic_ids) == 1 else None)

    gate_counts = {"ready": 0, "needs_llm": 0, "needs_engineer": 0}
    for rb in resolved_all:
        st = str(rb.get("gate_status") or "needs_engineer")
        if st in gate_counts:
            gate_counts[st] += 1

    bundle["logic_review_items"] = build_logic_review_items(
        logic_blocks,
        bundle.get("two_column_tables") or [],
        bundle.get("test_candidates") or [],
        bundle.get("issues") or [],
        bundle.get("condition_definitions") or [],
        bundle.get("alias_map") or [],
        footnotes,
        engineer_rows,
        supplemental_rows,
        resolved_all,
    )

    rep = build_spec_understanding_report(
        classified_files=bundle.get("classified_files") or [],
        logic_blocks=logic_blocks,
        condition_definitions=merged_condition_defs,
        issues=bundle.get("issues") or [],
        unresolved_items=bundle.get("unresolved_items") or [],
        two_column_tables=bundle.get("two_column_tables") or [],
        ingest_skipped=bundle.get("ingest_skipped") or [],
    )
    bundle["spec_understanding"] = rep
    summary = dict(bundle.get("summary") or {})
    summary["understanding_percent"] = rep["overall"]["understanding_percent"]
    summary["understanding_status"] = rep["overall"]["status"]
    summary["gate_ready"] = gate_counts["ready"]
    summary["gate_needs_llm"] = gate_counts["needs_llm"]
    summary["gate_needs_engineer"] = gate_counts["needs_engineer"]
    bundle["summary"] = summary

    loop_meta = dict(bundle.get("understanding_loop") or {})
    history = list(loop_meta.get("history") or [])
    history.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "logic_ids": refreshed,
            "gate_counts": gate_counts,
            "understanding_percent": rep["overall"]["understanding_percent"],
            "unresolved_cleared": unresolved_cleared,
        }
    )
    bundle["understanding_loop"] = {
        "last_rebuild_at": history[-1]["at"],
        "last_trigger": trigger,
        "history": history[-40:],
    }

    return {
        "ok": True,
        "trigger": trigger,
        "refreshed_logic_ids": refreshed,
        "gate_counts": gate_counts,
        "understanding_percent": rep["overall"]["understanding_percent"],
        "understanding_status": rep["overall"]["status"],
        "unresolved_cleared": unresolved_cleared,
        "footnote_materialized": mat_result.get("materialized_count", 0),
    }
