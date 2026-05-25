"""Build structured JSON Context Pack for M365 Copilot orchestrator."""

from __future__ import annotations

from typing import Any

from src.engine.coverage_gaps import analyze_coverage_gaps
from src.engine.path_tc_matrix import build_path_tc_matrix
from src.engine.signal_constraint_parser import (
    extract_signal_constraints_from_text,
    parse_structured_constraint,
)
from src.engine.term_role_classifier import build_term_role_index, classify_term
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview
from src.engine.logic_tree_renderer import render_tree_lines
from web.m365_brief import (
    _issues_for_logic,
    _logic_block,
    _logic_review_item,
    _missing_definitions,
)
from web.style_guide import style_reference_for_bundle
from web.project_memory import merge_project_memory, patterns_for_logic
from src.engine.verification_patterns import build_verification_matrix


def _signals_glossary(bundle: dict[str, Any], logic_id: str, control: str) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    engineer_defs = ai.get("engineer_definitions") or {}
    term_roles = build_term_role_index(bundle)
    footnotes = bundle.get("footnote_definitions") or []
    lb = _logic_block(bundle, logic_id) or {}
    unresolved = set(str(x).strip().upper() for x in lb.get("unresolved_refs") or [] if str(x).strip())

    names: set[str] = set()
    for term in unresolved:
        names.add(term)
    for term in engineer_defs:
        meta = engineer_defs.get(term) or {}
        if str(meta.get("logic_id") or logic_id) == logic_id or not meta.get("logic_id"):
            names.add(str(term).upper())
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        op = cand.get("operation") or {}
        for g in op.get("given") or []:
            if isinstance(g, dict) and g.get("signal"):
                names.add(str(g["signal"]).upper())

    out: list[dict[str, Any]] = []
    for name in sorted(names):
        meta = engineer_defs.get(name) or engineer_defs.get(name.lower()) or {}
        definition = str(meta.get("definition") or "")
        role_meta = term_roles.get(name) or term_roles.get(name.upper()) or {}
        role = role_meta.get("role") or classify_term(name, control_name=control, definition=definition)
        out.append(
            {
                "name": name,
                "role": role,
                "definition": definition,
                "source": meta.get("source") or "",
                "resolved": bool(definition),
            }
        )
    return out


def _paths_summary(bundle: dict[str, Any], logic_id: str) -> list[dict[str, Any]]:
    matrix = build_path_tc_matrix(bundle, logic_id)
    if not matrix.get("ok"):
        return []
    rows: list[dict[str, Any]] = []
    for path in matrix.get("paths") or []:
        rows.append(
            {
                "path_id": path.get("path_id"),
                "label": path.get("label"),
                "coverage_status": path.get("coverage_status"),
                "signals": path.get("signals") or [],
                "given_template": path.get("given_template") or [],
                "footnote_branch": path.get("footnote_branch"),
            }
        )
    return rows


def _testcase_snapshots(bundle: dict[str, Any], logic_id: str) -> list[dict[str, Any]]:
    preview = build_customer_testspec_preview(bundle, language="EN")
    rows: list[dict[str, Any]] = []
    for row in preview.get("rows") or []:
        if str(row.get("logic_id") or "") != logic_id:
            trace_logic = ""
            cid = row.get("candidate_id")
            for cand in bundle.get("test_candidates") or []:
                if cand.get("id") == cid:
                    trace_logic = str((cand.get("traceability") or {}).get("logic_block") or "")
                    break
            if trace_logic != logic_id:
                continue
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "test_function": row.get("test_function"),
                "event": row.get("event"),
                "use_case": row.get("use_case"),
                "operation": row.get("operation"),
                "expected_input": row.get("expected_input"),
                "expected_output": row.get("expected_output"),
                "review_status": row.get("review_status"),
                "logic_compliance": row.get("logic_compliance"),
            }
        )
    return rows


def _evidence_attachments(bundle: dict[str, Any], logic_id: str) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    attachments = ai.get("logic_attachments") or {}
    rows = attachments.get(logic_id) or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "file")
        mapped_kind = "screenshot" if kind == "image" else kind
        out.append(
            {
                "name": row.get("name"),
                "kind": mapped_kind,
                "preview": (row.get("preview") or "")[:2000],
                "definition_count": row.get("definition_count") or 0,
                "resolved_terms": row.get("resolved_terms") or [],
            }
        )
    return out


def _source_table_excerpt(item: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in item.get("table_rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "row_no": row.get("row_no"),
                "depth": row.get("depth"),
                "raw_condition": str(row.get("raw_condition") or "")[:200],
                "parser_reason": row.get("parser_reason") or row.get("detected_type"),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def build_context_pack(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    engineer_note: str = "",
    focus_term: str = "",
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured Context Pack JSON for Copilot plan/write phases."""
    lb = _logic_block(bundle, logic_id) or {}
    item = _logic_review_item(bundle, logic_id)
    control = str(lb.get("name") or item.get("control_name") or logic_id)
    expression = str(
        lb.get("raw_expression") or lb.get("expression") or item.get("raw_expression") or ""
    )
    parse_status = str(item.get("parse_status") or lb.get("parse_status") or "unknown")
    tree = lb.get("tree") or {}
    tree_lines = item.get("tree_lines") or []
    if not tree_lines and tree.get("type") and tree.get("type") != "empty":
        tree_lines = render_tree_lines(tree)

    parsed_constraints = extract_signal_constraints_from_text(
        engineer_note, focus_term=focus_term
    )
    structured = {
        k: parse_structured_constraint(v) or {"kind": "text", "value": v}
        for k, v in parsed_constraints.items()
    }
    ai = bundle.get("ai_assists") or {}
    engineer_defs = ai.get("engineer_definitions") or {}

    gaps = analyze_coverage_gaps(bundle, logic_id, engineer_definitions=engineer_defs)
    memory = merge_project_memory(bundle=bundle)
    verification = build_verification_matrix(bundle, logic_id)

    pack = {
        "schema_version": "1",
        "logic_id": logic_id,
        "logic": {
            "logic_id": logic_id,
            "control_name": control,
            "parse_status": parse_status,
            "raw_expression": expression[:8000],
            "condition_tree_lines": [str(line)[:200] for line in tree_lines[:40]],
            "source_table": _source_table_excerpt(item),
            "open_issues": [
                {
                    "type": i.get("type") or i.get("code"),
                    "message": str(i.get("message") or i.get("detail") or "")[:300],
                }
                for i in _issues_for_logic(bundle, logic_id, control)
            ],
            "missing_definitions": _missing_definitions(bundle, logic_id),
        },
        "signals": _signals_glossary(bundle, logic_id, control),
        "paths": _paths_summary(bundle, logic_id),
        "coverage_gaps": gaps,
        "testcases": _testcase_snapshots(bundle, logic_id),
        "engineer_input": {
            "raw_note": engineer_note.strip(),
            "focus_term": focus_term.strip(),
            "parsed_constraints": parsed_constraints,
            "structured_constraints": structured,
        },
        "evidence": {
            "attachments": _evidence_attachments(bundle, logic_id),
        },
        "style_reference": style_reference_for_bundle(bundle, cfg),
        "project_memory": {
            "shared_preconditions": memory.get("shared_preconditions") or [],
            "verification_patterns": patterns_for_logic(memory, logic_id),
            "signal_roles": memory.get("signal_roles") or {},
        },
        "verification_matrix": verification,
    }
    return pack


def cache_context_pack(
    bundle: dict[str, Any],
    logic_id: str,
    pack: dict[str, Any],
) -> dict[str, Any]:
    sessions = bundle.setdefault("ai_assists", {}).setdefault("copilot_sessions", {})
    entry = dict(sessions.get(logic_id) or {})
    entry["context_pack"] = pack
    sessions[logic_id] = entry
    return entry


def get_copilot_session(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    sessions = (bundle.get("ai_assists") or {}).get("copilot_sessions") or {}
    return dict(sessions.get(logic_id) or {})


def save_copilot_plan(bundle: dict[str, Any], logic_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    sessions = bundle.setdefault("ai_assists", {}).setdefault("copilot_sessions", {})
    entry = dict(sessions.get(logic_id) or {})
    entry["plan"] = plan
    sessions[logic_id] = entry
    return entry


def save_copilot_drafts(bundle: dict[str, Any], logic_id: str, drafts: dict[str, Any]) -> dict[str, Any]:
    sessions = bundle.setdefault("ai_assists", {}).setdefault("copilot_sessions", {})
    entry = dict(sessions.get(logic_id) or {})
    entry["drafts"] = drafts
    sessions[logic_id] = entry
    return entry
