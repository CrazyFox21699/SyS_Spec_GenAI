"""Bind logic blocks, transitions, diagram edges, and state outputs to final candidates."""

from __future__ import annotations

import re
from typing import Any


def _normalize(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _format_source(src: dict[str, Any] | None) -> str:
    if not src:
        return ""
    parts = [
        src.get("file") or src.get("document") or "",
        src.get("sheet") or "",
        src.get("table") or src.get("table_id") or "",
        src.get("state") or "",
        f"row {src.get('row')}" if src.get("row") else "",
        f"paragraph {src.get('paragraph')}" if src.get("paragraph") else "",
    ]
    return " / ".join(str(p) for p in parts if p)


def _logic_bindings(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in bundle.get("logic_blocks") or []:
        lid = str(row.get("id") or "").strip()
        if lid:
            out[lid] = row
    return out


def _transition_bindings(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in bundle.get("transitions") or []:
        tid = str(row.get("id") or "").strip()
        if tid:
            out[tid] = row
    return out


def _diagram_edges(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return list((bundle.get("diagram_semantics") or {}).get("edges") or [])


def _state_outputs_by_state(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in bundle.get("state_rules") or []:
        state = _normalize((row.get("source") or {}).get("state"))
        if not state:
            continue
        out.setdefault(state, []).append(row)
    return out


def _find_logic_for_candidate(
    candidate: dict[str, Any],
    logic_by_id: dict[str, dict[str, Any]],
    logic_blocks: list[dict[str, Any]],
    transitions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    trace = candidate.get("traceability") or {}
    found: list[dict[str, Any]] = []
    for key in ("logic_block", "logic"):
        lid = str(trace.get(key) or "").strip()
        if lid and lid in logic_by_id:
            found.append(logic_by_id[lid])
    if found:
        return found

    event = str(candidate.get("event") or "")
    use_case = str(candidate.get("use_case_description") or "")
    for block in logic_blocks:
        name = str(block.get("name") or "")
        if not name:
            continue
        if name in event or name in use_case or event == f"evaluate_{name}":
            found.append(block)
    if not found and transitions:
        transition_sources = {
            (
                str((row.get("source") or {}).get("file") or ""),
                str((row.get("source") or {}).get("sheet") or ""),
            )
            for row in transitions
        }
        for block in logic_blocks:
            source = block.get("source") or {}
            key = (str(source.get("file") or ""), str(source.get("sheet") or ""))
            if key in transition_sources:
                found.append(block)
    if not found and len(logic_blocks) == 1:
        found.append(logic_blocks[0])
    # preserve order, dedupe by id
    seen = set()
    out = []
    for row in found:
        lid = str(row.get("id") or "")
        if lid in seen:
            continue
        seen.add(lid)
        out.append(row)
    return out


def _find_transition_for_candidate(candidate: dict[str, Any], transition_by_id: dict[str, dict[str, Any]], transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace = candidate.get("traceability") or {}
    tid = str(trace.get("transition") or "").strip()
    if tid and tid in transition_by_id:
        return [transition_by_id[tid]]

    event = _normalize(candidate.get("event"))
    states = { _normalize(item.get("current_state")) for item in candidate.get("precondition") or [] if isinstance(item, dict) and item.get("current_state") }
    out = []
    for row in transitions:
        row_event = _normalize(row.get("event"))
        from_state = _normalize(row.get("from_state"))
        if event and row_event and event == row_event:
            out.append(row)
        elif states and from_state in states:
            out.append(row)
    seen = set()
    deduped = []
    for row in out:
        tid = str(row.get("id") or "")
        if tid in seen:
            continue
        seen.add(tid)
        deduped.append(row)
    return deduped[:3]


def _find_edges_for_transitions(edges: list[dict[str, Any]], transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transition_ids = {str(row.get("id") or "") for row in transitions if row.get("id")}
    state_keys = {
        (
            _normalize(row.get("from_state")),
            _normalize(row.get("to_state")),
            _normalize(row.get("event")),
        )
        for row in transitions
    }
    out = []
    for edge in edges:
        edge_ids = {str(value) for value in edge.get("transition_ids") or []}
        edge_key = (
            _normalize(edge.get("from_state")),
            _normalize(edge.get("to_state")),
            _normalize(edge.get("event")),
        )
        if transition_ids & edge_ids or edge_key in state_keys:
            out.append(edge)
    return out


def _find_state_outputs(transitions: list[dict[str, Any]], outputs_by_state: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for row in transitions:
        to_state = _normalize(row.get("to_state"))
        out.extend(outputs_by_state.get(to_state, []))
    seen = set()
    deduped = []
    for row in out:
        key = (
            str((row.get("source") or {}).get("state") or ""),
            str(row.get("name") or ""),
            str(row.get("expression") or row.get("definition") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:8]


def _binding_summary(binding: dict[str, Any]) -> tuple[list[str], list[str]]:
    summary_parts: list[str] = []
    evidence_lines: list[str] = []

    if binding["logic_blocks"]:
        summary_parts.append("logic")
        for row in binding["logic_blocks"][:2]:
            evidence_lines.append(f"logic:{row.get('name') or row.get('id')} -> {str(row.get('raw_expression') or '')[:140]}")
            source = _format_source(row.get("source"))
            if source:
                evidence_lines.append(f"  source: {source}")
    if binding["transitions"]:
        summary_parts.append("transition")
        for row in binding["transitions"][:2]:
            evidence_lines.append(
                f"transition:{row.get('id')} {row.get('from_state') or '?'} -> {row.get('to_state') or '?'} [{row.get('event') or ''}]"
            )
            source = _format_source(row.get("source"))
            if source:
                evidence_lines.append(f"  source: {source}")
    if binding["diagram_edges"]:
        summary_parts.append("diagram")
        for row in binding["diagram_edges"][:2]:
            evidence_lines.append(
                f"diagram:{row.get('from_state') or '?'} -> {row.get('to_state') or '?'} [{row.get('event') or ''}]"
            )
            if row.get("evidence_refs"):
                evidence_lines.append(f"  evidence: {', '.join(str(x) for x in (row.get('evidence_refs') or [])[:3])}")
    if binding["state_outputs"]:
        summary_parts.append("outputs")
        for row in binding["state_outputs"][:3]:
            evidence_lines.append(
                f"output:{(row.get('source') or {}).get('state') or '?'} {row.get('name') or ''} = {row.get('expression') or row.get('definition') or ''}"
            )
    return summary_parts, evidence_lines


def build_candidate_evidence_bindings(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    logic_by_id = _logic_bindings(bundle)
    transition_by_id = _transition_bindings(bundle)
    logic_blocks = list(bundle.get("logic_blocks") or [])
    transitions = list(bundle.get("transitions") or [])
    edges = _diagram_edges(bundle)
    outputs_by_state = _state_outputs_by_state(bundle)

    bindings: dict[str, dict[str, Any]] = {}
    for candidate in bundle.get("test_candidates") or []:
        candidate_id = str(candidate.get("id") or "").strip()
        if not candidate_id:
            continue
        bound_transitions = _find_transition_for_candidate(candidate, transition_by_id, transitions)
        bound_logic = _find_logic_for_candidate(candidate, logic_by_id, logic_blocks, bound_transitions)
        bound_edges = _find_edges_for_transitions(edges, bound_transitions)
        bound_outputs = _find_state_outputs(bound_transitions, outputs_by_state)
        summary_tags, evidence_lines = _binding_summary(
            {
                "logic_blocks": bound_logic,
                "transitions": bound_transitions,
                "diagram_edges": bound_edges,
                "state_outputs": bound_outputs,
            }
        )
        logic_id = str(bound_logic[0].get("id") or "") if bound_logic else ""
        control_name = str(bound_logic[0].get("name") or "") if bound_logic else ""
        bindings[candidate_id] = {
            "logic_id": logic_id,
            "control_name": control_name,
            "logic_blocks": [
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "raw_expression": row.get("raw_expression"),
                    "source": _format_source(row.get("source")),
                }
                for row in bound_logic
            ],
            "transitions": [
                {
                    "id": row.get("id"),
                    "from_state": row.get("from_state"),
                    "to_state": row.get("to_state"),
                    "event": row.get("event"),
                    "raw_condition": row.get("raw_condition"),
                    "source": _format_source(row.get("source")),
                }
                for row in bound_transitions
            ],
            "diagram_edges": [
                {
                    "from_state": row.get("from_state"),
                    "to_state": row.get("to_state"),
                    "event": row.get("event"),
                    "semantic_type": row.get("semantic_type"),
                    "evidence_refs": row.get("evidence_refs") or [],
                    "transition_ids": row.get("transition_ids") or [],
                }
                for row in bound_edges
            ],
            "state_outputs": [
                {
                    "state": (row.get("source") or {}).get("state"),
                    "name": row.get("name"),
                    "expression": row.get("expression") or row.get("definition"),
                    "source": _format_source(row.get("source")),
                }
                for row in bound_outputs
            ],
            "summary_tags": summary_tags,
            "evidence_summary_lines": evidence_lines,
            "evidence_summary": "\n".join(evidence_lines),
        }
    return bindings
