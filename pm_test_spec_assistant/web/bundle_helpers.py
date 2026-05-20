"""Load and enrich persisted analysis bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.engine.logic_review_builder import build_logic_review_items
from src.engine.evidence_registry import build_evidence_registry
from src.engine.spec_understanding_report import build_spec_understanding_report
from src.engine.use_case_text import sanitize_candidates_use_cases
from src.engine.document_graph_builder import build_document_graph


def _engineer_definitions(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    defs = ai.get("engineer_definitions") or {}
    rows = []
    for name, meta in defs.items():
        rows.append(
            {
                "name": name,
                "definition": meta.get("definition", ""),
                "source": {
                    "file": "engineer_clarification",
                    "table": meta.get("logic_id", ""),
                    "row": None,
                },
            }
        )
    return rows


def _supplemental_definitions(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    grouped = ai.get("supplemental_definitions") or {}
    rows = []
    for defs in grouped.values():
        for row in defs or []:
            rows.append(dict(row))
    return rows


def ensure_spec_understanding(bundle: dict[str, Any]) -> dict[str, Any]:
    """Rebuild spec_understanding when missing (older jobs on disk)."""
    if bundle.get("spec_understanding"):
        return bundle
    rep = build_spec_understanding_report(
        classified_files=bundle.get("classified_files") or [],
        logic_blocks=bundle.get("logic_blocks") or [],
        condition_definitions=bundle.get("condition_definitions") or [],
        issues=bundle.get("issues") or [],
        unresolved_items=bundle.get("unresolved_items") or [],
        two_column_tables=bundle.get("two_column_tables") or [],
        ingest_skipped=bundle.get("ingest_skipped") or [],
    )
    bundle = dict(bundle)
    bundle["spec_understanding"] = rep
    summary = dict(bundle.get("summary") or {})
    summary["understanding_percent"] = rep["overall"]["understanding_percent"]
    summary["understanding_status"] = rep["overall"]["status"]
    bundle["summary"] = summary
    return bundle


def ensure_logic_review_items(bundle: dict[str, Any]) -> dict[str, Any]:
    """Rebuild logic_review_items when missing or from an older schema."""
    items = bundle.get("logic_review_items") or []
    has_engineer_defs = bool(((bundle.get("ai_assists") or {}).get("engineer_definitions") or {}))
    has_supp_defs = bool(((bundle.get("ai_assists") or {}).get("supplemental_definitions") or {}))
    if (
        items
        and all(
            "trace_rows" in item and "tree_model" in item and "review_resolved_terms" in item
            for item in items
        )
        and not has_engineer_defs
        and not has_supp_defs
    ):
        return bundle
    bundle = dict(bundle)
    bundle["logic_review_items"] = build_logic_review_items(
        bundle.get("logic_blocks") or [],
        bundle.get("two_column_tables") or [],
        bundle.get("test_candidates") or [],
        bundle.get("issues") or [],
        bundle.get("condition_definitions") or [],
        bundle.get("alias_map") or [],
        bundle.get("footnote_definitions") or [],
        _engineer_definitions(bundle),
        _supplemental_definitions(bundle),
    )
    return bundle


def ensure_evidence_registry(bundle: dict[str, Any]) -> dict[str, Any]:
    """Rebuild evidence_registry when missing (older jobs on disk)."""
    if bundle.get("evidence_registry") and bundle["evidence_registry"].get("items"):
        return bundle
    reg = build_evidence_registry(
        footnote_definitions=bundle.get("footnote_definitions") or [],
        alias_map=bundle.get("alias_map") or [],
        logic_blocks=bundle.get("logic_blocks") or [],
        condition_definitions=bundle.get("condition_definitions") or [],
        diagram_meta=bundle.get("diagrams") or [],
    )
    bundle = dict(bundle)
    bundle["evidence_registry"] = reg
    summary = dict(bundle.get("summary") or {})
    summary["evidence_refs_total"] = reg.get("total", 0)
    bundle["summary"] = summary
    return bundle


def ensure_document_graph(bundle: dict[str, Any]) -> dict[str, Any]:
    """Recompute the document graph (preserving user-defined edges)."""
    graph = build_document_graph(bundle)
    bundle = dict(bundle)
    bundle["document_graph"] = graph
    summary = dict(bundle.get("summary") or {})
    summary["document_graph_nodes"] = graph["summary"].get("node_count", 0)
    summary["document_graph_edges"] = (
        graph["summary"].get("edge_count", 0) + graph["summary"].get("user_edge_count", 0)
    )
    bundle["summary"] = summary
    return bundle


def ensure_enriched_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    bundle = ensure_logic_review_items(bundle)
    bundle = sanitize_candidates_use_cases(bundle)
    bundle = ensure_spec_understanding(bundle)
    bundle = ensure_evidence_registry(bundle)
    bundle = ensure_document_graph(bundle)
    return bundle


def bundle_path_for_job(output_root: Path, job_id: str) -> Path | None:
    path = output_root / job_id / "ui_bundle.yaml"
    return path if path.exists() else None
