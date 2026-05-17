"""Build a deterministic semantic graph for state-machine diagrams and OCR-derived transitions."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

_STATE_SPLIT_RE = re.compile(r"[^A-Z0-9]+")
_STATE_LINE_RE = re.compile(r"^(?:STATE|MODE)?\s*:?\s*([A-Z][A-Z0-9 _/-]{1,40})$", re.I)


def _normalize_state_name(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    tokens = [part for part in _STATE_SPLIT_RE.split(text) if part]
    if not tokens:
        return ""
    return "_".join(tokens)


def _source_label(src: dict[str, Any] | None) -> str:
    if not isinstance(src, dict):
        return ""
    parts = [
        src.get("file") or src.get("document") or "",
        src.get("kind") or "",
        src.get("table") or src.get("table_id") or "",
        f"row {src.get('row')}" if src.get("row") else "",
        f"paragraph {src.get('paragraph')}" if src.get("paragraph") else "",
        f"page {src.get('page')}" if src.get("page") else "",
    ]
    return " / ".join(p for p in parts if p)


def _edge_semantic_type(transition: dict[str, Any]) -> str:
    derivation = str(transition.get("derivation") or "")
    if derivation in {
        "diagram_text",
        "diagram_image_ocr",
        "pdf_embedded_image_ocr",
        "docx_embedded_image_ocr",
        "excel_drawing_connector",
    }:
        return "explicit_arrow"
    if derivation in {"diagram_state_rule", "paragraph_state_rule"}:
        return "rule_inferred"
    if "transition" in derivation or str(transition.get("event") or "").lower().endswith("transition"):
        return "explicit_transition"
    return "state_rule"


def _extract_state_mentions(diagrams: list[dict[str, Any]]) -> dict[str, list[str]]:
    mentions: dict[str, list[str]] = defaultdict(list)
    for diagram in diagrams:
        text = str(diagram.get("ocr_text") or "")
        source = _source_label(
            {
                "file": diagram.get("parent_document") or diagram.get("name") or diagram.get("file"),
                "kind": diagram.get("source_kind") or "diagram_ocr",
                "table": diagram.get("sheet"),
                "page": diagram.get("page"),
            }
        )
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = _STATE_LINE_RE.match(line)
            if not m:
                continue
            norm = _normalize_state_name(m.group(1))
            if not norm:
                continue
            mentions[norm].append(source or line)
    return mentions


def build_diagram_semantic_graph(
    *,
    transitions: list[dict[str, Any]],
    diagrams: list[dict[str, Any]] | None = None,
    state_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a state graph with normalized nodes and evidence-backed edges."""
    diagrams = diagrams or []
    state_rules = state_rules or []
    nodes: dict[str, dict[str, Any]] = {}
    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    state_mentions = _extract_state_mentions(diagrams)

    def ensure_node(state_name: str, *, source_type: str, evidence: str = "") -> None:
        norm = _normalize_state_name(state_name)
        if not norm:
            return
        row = nodes.setdefault(
            norm,
            {
                "state": norm,
                "labels": set(),
                "source_types": set(),
                "evidence_refs": set(),
            },
        )
        row["labels"].add(str(state_name).strip())
        row["source_types"].add(source_type)
        if evidence:
            row["evidence_refs"].add(evidence)

    for transition in transitions:
        from_state = _normalize_state_name(transition.get("from_state"))
        to_state = _normalize_state_name(transition.get("to_state"))
        event = str(transition.get("event") or "").strip() or "transition"
        if not from_state and not to_state:
            continue
        ensure_node(from_state or "UNKNOWN", source_type="transition", evidence=_source_label(transition.get("source")))
        ensure_node(to_state or "UNKNOWN", source_type="transition", evidence=_source_label(transition.get("source")))
        key = (from_state or "UNKNOWN", to_state or "UNKNOWN", event)
        edge = edge_map.setdefault(
            key,
            {
                "from_state": from_state or "UNKNOWN",
                "to_state": to_state or "UNKNOWN",
                "event": event,
                "semantic_type": _edge_semantic_type(transition),
                "conditions": [],
                "source_derivations": set(),
                "evidence_refs": set(),
                "confidence_levels": set(),
                "review_required": False,
                "transition_ids": [],
            },
        )
        raw_condition = str(transition.get("raw_condition") or "").strip()
        if raw_condition and raw_condition not in edge["conditions"]:
            edge["conditions"].append(raw_condition)
        derivation = str(transition.get("derivation") or "")
        if derivation:
            edge["source_derivations"].add(derivation)
        evidence = _source_label(transition.get("source"))
        if evidence:
            edge["evidence_refs"].add(evidence)
        confidence = str(transition.get("confidence") or "")
        if confidence:
            edge["confidence_levels"].add(confidence)
        if transition.get("review_required"):
            edge["review_required"] = True
        if transition.get("id"):
            edge["transition_ids"].append(str(transition.get("id")))

    for state_name, refs in state_mentions.items():
        ensure_node(state_name, source_type="ocr_state_label", evidence=refs[0] if refs else "")

    for row in state_rules:
        name = _normalize_state_name(row.get("name"))
        if not name:
            continue
        ensure_node(name, source_type="state_rule", evidence=_source_label(row.get("source")))

    normalized_nodes = []
    for key, node in sorted(nodes.items()):
        normalized_nodes.append(
            {
                "state": key,
                "labels": sorted({label for label in node["labels"] if label}),
                "source_types": sorted(node["source_types"]),
                "evidence_refs": sorted(node["evidence_refs"]),
                "ocr_mentioned": key in state_mentions,
            }
        )

    normalized_edges = []
    for edge in edge_map.values():
        normalized_edges.append(
            {
                "from_state": edge["from_state"],
                "to_state": edge["to_state"],
                "event": edge["event"],
                "semantic_type": edge["semantic_type"],
                "conditions": edge["conditions"][:6],
                "source_derivations": sorted(edge["source_derivations"]),
                "evidence_refs": sorted(edge["evidence_refs"]),
                "confidence_levels": sorted(edge["confidence_levels"]),
                "review_required": edge["review_required"],
                "transition_ids": edge["transition_ids"],
            }
        )

    summary = {
        "states_total": len(normalized_nodes),
        "edges_total": len(normalized_edges),
        "explicit_edges": sum(1 for row in normalized_edges if row["semantic_type"] in {"explicit_arrow", "explicit_transition"}),
        "rule_inferred_edges": sum(1 for row in normalized_edges if row["semantic_type"] == "rule_inferred"),
        "ocr_state_mentions": sum(1 for row in normalized_nodes if row["ocr_mentioned"]),
    }

    return {
        "states": normalized_nodes,
        "edges": normalized_edges,
        "summary": summary,
        "graph_built": bool(normalized_edges or normalized_nodes),
    }
