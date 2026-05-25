"""Review workbench helpers for final TestSpec, evidence graph, and definition inbox."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from src.exporters.customer_testspec_exporter import build_customer_testspec_preview


def _normalize_term(term: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(term or "").upper())


def _engineer_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    defs = ai.get("engineer_definitions") or {}
    rows = []
    for name, meta in defs.items():
        rows.append(
            {
                "name": name,
                "definition": meta.get("definition", ""),
                "logic_id": meta.get("logic_id", ""),
                "source": {
                    "file": "engineer_clarification",
                    "table": meta.get("logic_id", ""),
                    "row": None,
                },
                "kind": "engineer_note",
            }
        )
    return rows


def _supplemental_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    grouped = ai.get("supplemental_definitions") or {}
    rows = []
    for defs in grouped.values():
        for row in defs or []:
            rows.append({**row, "kind": "added_file"})
    return rows


def _format_source(src: dict[str, Any] | None) -> str:
    if not src:
        return ""
    parts = [
        src.get("file") or src.get("document") or "",
        src.get("sheet") or "",
        src.get("table") or src.get("table_id") or "",
        f"row {src.get('row')}" if src.get("row") else "",
    ]
    return " / ".join(p for p in parts if p)


def _definition_match_mode(term: str, row: dict[str, Any]) -> str:
    name = str(row.get("name") or "").strip()
    if not name:
        return "unknown"
    if name == term:
        return "exact"
    if _normalize_term(name) == _normalize_term(term):
        return "normalized"
    return "related"


def _reason_payload(term: str, definitions: list[dict[str, Any]], *, missing: bool) -> dict[str, str]:
    if missing:
        return {
            "reason_code": "not_found",
            "reason_detail": f"No trusted definition for `{term}` was found in the uploaded spec or added review files yet.",
            "recommended_action": "Attach a define sheet, code snippet, or engineer clarification for this term.",
        }

    match_modes = {str(row.get("match_mode") or "") for row in definitions}
    unique_defs = {str(row.get("definition") or "").strip() for row in definitions if str(row.get("definition") or "").strip()}
    kinds = {str(row.get("kind") or "") for row in definitions}
    if len(unique_defs) > 1:
        return {
            "reason_code": "conflicting_definitions",
            "reason_detail": f"`{term}` has multiple different definitions across the available sources.",
            "recommended_action": "Compare the conflicting rows below and keep only the trusted one for final approval.",
        }
    if "normalized" in match_modes:
        return {
            "reason_code": "normalized_match",
            "reason_detail": f"`{term}` was matched after normalizing punctuation or separators.",
            "recommended_action": "Verify that the normalized name really refers to the same condition before final approval.",
        }
    if "engineer_note" in kinds:
        return {
            "reason_code": "engineer_note_only",
            "reason_detail": f"`{term}` is currently resolved from an engineer clarification note.",
            "recommended_action": "Keep it under review until the note is accepted or confirmed by a source document.",
        }
    if "added_file" in kinds:
        return {
            "reason_code": "added_file_only",
            "reason_detail": f"`{term}` was resolved from a file added during review, not from the original uploaded spec set.",
            "recommended_action": "Confirm this added file is an acceptable source for the final workbook.",
        }
    return {
        "reason_code": "spec_definition_found",
        "reason_detail": f"`{term}` has a definition in the uploaded specification set.",
        "recommended_action": "Review the linked final workbook rows.",
    }


def _append_unique(rows: list[dict[str, Any]], row: dict[str, Any], seen: set[tuple[str, str, str]]) -> None:
    key = (
        str(row.get("name") or ""),
        str(row.get("definition") or ""),
        str(_format_source(row.get("source"))),
    )
    if key in seen:
        return
    seen.add(key)
    rows.append(row)


def _definition_lookup(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_by_key: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    all_rows = [
        *({**row, "kind": "spec_definition"} for row in bundle.get("condition_definitions") or []),
        *({**row, "kind": "signal_registry"} for row in (bundle.get("signals") or [])),
        *_supplemental_rows(bundle),
        *_engineer_rows(bundle),
    ]
    for row in all_rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        for key in {name, _normalize_term(name)}:
            if not key:
                continue
            _append_unique(lookup[key], row, seen_by_key[key])
    for sig in bundle.get("signals") or []:
        name = str(sig.get("name") or "").strip()
        if not name:
            continue
        row = {
            "name": name,
            "definition": sig.get("definition") or sig.get("description") or name,
            "source": sig.get("source") or {},
            "kind": "signal_registry",
        }
        for key in {name, _normalize_term(name)}:
            if key:
                _append_unique(lookup[key], row, seen_by_key[key])
    return lookup


def build_evidence_graph(bundle: dict[str, Any]) -> dict[str, Any]:
    lookup = _definition_lookup(bundle)
    aliases = bundle.get("alias_map") or []
    footnotes = bundle.get("footnote_definitions") or []
    workbook = build_customer_testspec_preview(bundle, language="EN")
    rows_by_logic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in workbook["rows"]:
        rows_by_logic[str(row.get("logic_id") or "")].append(row)

    nodes: dict[str, dict[str, Any]] = {}

    def ensure_node(term: str) -> dict[str, Any]:
        key = term.strip()
        if key not in nodes:
            rows = lookup.get(key, []) or lookup.get(_normalize_term(key), [])
            nodes[key] = {
                "term": key,
                "normalized_term": _normalize_term(key),
                "definitions": [
                    {
                        "kind": row.get("kind", "spec_definition"),
                        "definition": row.get("definition", ""),
                        "source": _format_source(row.get("source")),
                        "logic_id": row.get("logic_id", ""),
                        "match_mode": _definition_match_mode(key, row),
                    }
                    for row in rows
                ],
                "logic_groups": [],
                "candidate_ids": [],
                "aliases": [],
                "footnotes": [],
                "status": "missing_definition",
            }
        return nodes[key]

    for item in bundle.get("logic_review_items") or []:
        logic_id = str(item.get("logic_id") or "")
        control_name = str(item.get("control_name") or "")
        for trace in item.get("trace_rows") or []:
            node = ensure_node(str(trace.get("term") or ""))
            node["logic_groups"].append(
                {
                    "logic_id": logic_id,
                    "control_name": control_name,
                    "trace_status": trace.get("status"),
                }
            )
            node["candidate_ids"].extend(
                [
                    str(row.get("candidate_id") or "")
                    for row in rows_by_logic.get(logic_id, [])
                    if row.get("candidate_id")
                ]
            )
            node["aliases"].extend(trace.get("aliases") or [])
            node["footnotes"].extend(trace.get("footnotes") or [])
            if trace.get("status") == "needs_review" and node["status"] != "resolved":
                node["status"] = "resolved_needs_review"

    for alias in aliases:
        target = str(alias.get("target") or "").strip()
        if not target:
            continue
        node = ensure_node(target)
        node["aliases"].append(
            {
                "alias": alias.get("alias"),
                "target": alias.get("target"),
                "source": _format_source(alias.get("source")),
            }
        )
        if node["definitions"] and node["status"] == "missing_definition":
            node["status"] = "resolved"

    for footnote in footnotes:
        term = str(footnote.get("condition_name") or "").strip()
        if not term:
            continue
        node = ensure_node(term)
        node["footnotes"].append(
            {
                "ref": footnote.get("ref"),
                "definition": footnote.get("definition", ""),
                "source": _format_source(footnote.get("source")),
            }
        )
        if footnote.get("definition") and node["status"] == "missing_definition":
            node["status"] = "resolved_needs_review"

    for node in nodes.values():
        node["logic_groups"] = sorted(
            {
                (g.get("logic_id", ""), g.get("control_name", ""), g.get("trace_status", ""))
                for g in node["logic_groups"]
            }
        )
        node["logic_groups"] = [
            {"logic_id": lid, "control_name": name, "trace_status": status}
            for lid, name, status in node["logic_groups"]
        ]
        node["candidate_ids"] = sorted({cid for cid in node["candidate_ids"] if cid})
        node["aliases"] = sorted(
            {
                (
                    str(a.get("alias") or ""),
                    str(a.get("target") or ""),
                    str(a.get("source") or ""),
                )
                for a in node["aliases"]
            }
        )
        node["aliases"] = [
            {"alias": alias, "target": target, "source": source}
            for alias, target, source in node["aliases"]
        ]
        node["footnotes"] = sorted(
            {
                (
                    str(f.get("ref") or ""),
                    str(f.get("definition") or ""),
                    str(f.get("source") or ""),
                )
                for f in node["footnotes"]
            }
        )
        node["footnotes"] = [
            {"ref": ref, "definition": definition, "source": source}
            for ref, definition, source in node["footnotes"]
        ]
        if node["definitions"]:
            kinds = {d.get("kind") for d in node["definitions"]}
            if "spec_definition" in kinds:
                node["status"] = "resolved"
            elif "added_file" in kinds or "engineer_note" in kinds:
                node["status"] = "resolved_needs_review"
        reason = _reason_payload(node["term"], node["definitions"], missing=not node["definitions"])
        node["reason_code"] = reason["reason_code"]
        node["reason_detail"] = reason["reason_detail"]
        node["recommended_action"] = reason["recommended_action"]

    term_nodes = sorted(nodes.values(), key=lambda row: (row["status"] != "missing_definition", row["term"]))
    return {
        "terms": term_nodes,
        "summary": {
            "terms_total": len(term_nodes),
            "terms_missing_definition": sum(1 for row in term_nodes if row["status"] == "missing_definition"),
            "terms_resolved": sum(1 for row in term_nodes if row["status"] == "resolved"),
            "terms_resolved_needs_review": sum(1 for row in term_nodes if row["status"] == "resolved_needs_review"),
        },
    }


def build_definition_inbox(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    evidence = build_evidence_graph(bundle)
    item = next(
        (row for row in bundle.get("logic_review_items") or [] if str(row.get("logic_id")) == logic_id),
        None,
    )
    if not item:
        raise KeyError(f"Logic review item not found: {logic_id}")

    evidence_by_term = {row["term"]: row for row in evidence["terms"]}
    ai = bundle.get("ai_assists") or {}
    attachments = list((ai.get("logic_attachments") or {}).get(logic_id, []) or [])
    supplemental = list((ai.get("supplemental_definitions") or {}).get(logic_id, []) or [])
    query_history = list((ai.get("definition_queries") or {}).get(logic_id, []) or [])
    ai_term_hints = {
        str(row.get("term") or ""): row
        for row in ((ai.get("term_resolution_hints") or {}).get(logic_id) or [])
        if str(row.get("term") or "").strip()
    }

    terms = []
    used_terms = {str(trace.get("term") or "") for trace in item.get("trace_rows") or []}
    for trace in item.get("trace_rows") or []:
        term = str(trace.get("term") or "")
        node = evidence_by_term.get(term, {})
        status = node.get("status", "missing_definition")
        if status == "resolved":
            resolution = "definition_found"
            next_action = "Review the final workbook row."
        elif status == "resolved_needs_review":
            resolution = "added_context_found"
            next_action = "Confirm this added definition is acceptable for final approval."
        else:
            resolution = "missing_definition"
            next_action = "Attach a define sheet, code snippet, or engineer clarification for this term."
        reason = _reason_payload(term, node.get("definitions", []), missing=not node.get("definitions"))
        ai_hint = ai_term_hints.get(term)
        terms.append(
            {
                "term": term,
                "resolution": resolution,
                "next_action": next_action,
                "reason_code": reason["reason_code"],
                "reason_detail": reason["reason_detail"],
                "recommended_action": reason["recommended_action"],
                "preview": trace.get("preview", ""),
                "definitions": node.get("definitions", []),
                "aliases": node.get("aliases", []),
                "footnotes": node.get("footnotes", []),
                "logic_groups": node.get("logic_groups", []),
                "candidate_ids": node.get("candidate_ids", []),
                "ai_hint": ai_hint,
            }
        )

    unused_added = [
        {
            "name": row.get("name", ""),
            "definition": row.get("definition", ""),
            "source": _format_source(row.get("source")),
        }
        for row in supplemental
        if str(row.get("name") or "") not in used_terms
    ]

    return {
        "logic_id": logic_id,
        "control_name": item.get("control_name", ""),
        "terms": terms,
        "attachments": attachments,
        "unused_added_definitions": unused_added,
        "query_history": query_history[-8:],
    }


def build_capability_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    logic_items = bundle.get("logic_review_items") or []
    transitions = bundle.get("transitions") or []
    diagrams = bundle.get("diagrams") or []
    semantics = bundle.get("diagram_semantics") or {}
    image_transitions = [row for row in transitions if str(row.get("derivation") or "").startswith("diagram_image")]
    narrative_transitions = [row for row in transitions if row.get("derivation") == "diagram_text"]
    table_transitions = [row for row in transitions if row.get("derivation") not in {"diagram_text", "diagram_image_metadata"}]
    footnotes = bundle.get("footnote_definitions") or []
    preview = build_customer_testspec_preview(bundle, language="EN")
    rows = preview["rows"]
    condition_rows = bundle.get("condition_definitions") or []
    value_like_defs = [
        row
        for row in condition_rows
        if any(token in str(row.get("definition") or "") for token in ("=", ">=", "<=", "TRUE", "FALSE"))
    ]
    review_required_rows = [row for row in rows if str(row.get("engineer_confirmation_required") or "").lower() == "yes"]
    return {
        "logic": {
            "groups_total": len(logic_items),
            "groups_ok": sum(1 for item in logic_items if str(item.get("parse_status") or "") == "ok"),
            "groups_partial": sum(1 for item in logic_items if str(item.get("parse_status") or "") == "partial"),
            "groups_failed": sum(1 for item in logic_items if str(item.get("parse_status") or "") == "failed"),
        },
        "definitions": {
            "spec_definitions": len(condition_rows),
            "footnotes_linked": len(footnotes),
            "conditions_with_value_text": len(value_like_defs),
        },
        "transitions": {
            "total": len(transitions),
            "from_tables_or_rules": len(table_transitions),
            "from_narrative_text": len(narrative_transitions),
            "diagram_images_only": len(image_transitions),
            "diagram_shape_semantic_parse": bool(semantics.get("graph_built")),
            "diagram_semantic_edges": (semantics.get("summary") or {}).get("edges_total", 0),
        },
        "ocr": {
            "diagram_assets": len(diagrams),
            "diagram_assets_with_ocr_text": sum(1 for row in diagrams if str(row.get("ocr_text") or "").strip()),
            "local_ocr_available": any(bool(row.get("ocr_available")) for row in diagrams) if diagrams else False,
        },
        "workbook": {
            "rows_total": len(rows),
            "rows_need_engineer_answer": len(review_required_rows),
            "rows_with_ai_overlay": sum(1 for row in rows if row.get("ai_provider")),
        },
        "limits": [
            "Diagram semantics currently come from OCR text, explicit arrows, and rule-style statements; purely visual arrows without readable text are still weak.",
            "Transitions are extracted from tables, text rules, and narrative arrows; complex visual layouts without text are not trusted automatically.",
            "Condition values embedded inside definition text are detected heuristically, not fully normalized into structured operands yet.",
        ],
    }


def build_ai_queue(bundle: dict[str, Any], *, language: str = "EN") -> dict[str, Any]:
    preview = build_customer_testspec_preview(bundle, language=language)
    rows_by_logic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in preview["rows"]:
        if row.get("logic_id"):
            rows_by_logic[str(row.get("logic_id"))].append(row)
    ai = bundle.get("ai_assists") or {}
    logic_reviews = ai.get("logic_reviews") or {}
    logic_attachments = ai.get("logic_attachments") or {}
    engineer_notes = ai.get("engineer_notes") or {}

    queue_rows: list[dict[str, Any]] = []
    for item in bundle.get("logic_review_items") or []:
        logic_id = str(item.get("logic_id") or "")
        related_rows = rows_by_logic.get(logic_id, [])
        missing_terms = [
            str(row.get("term") or "")
            for row in item.get("trace_rows") or []
            if str(row.get("status") or "") == "missing"
        ]
        ai_review = logic_reviews.get(logic_id) or {}
        note = str(engineer_notes.get(logic_id) or "").strip()
        attachments = list(logic_attachments.get(logic_id) or [])
        related_statuses = Counter(str(row.get("review_status") or "pending").lower() for row in related_rows)

        if not related_rows:
            queue_status = "no_rows"
            queue_reason = "No final workbook rows are linked to this logic group yet."
        elif missing_terms:
            queue_status = "blocked_missing_definition"
            queue_reason = f"Missing trusted definitions for: {', '.join(missing_terms[:4])}"
        elif str(item.get("parse_status") or "") != "ok":
            queue_status = "needs_engineer_answer"
            queue_reason = "The deterministic parser marked this logic group as partial or failed."
        elif ai_review and any(str(row.get("engineer_confirmation_required") or "").lower() == "yes" for row in related_rows):
            queue_status = "needs_engineer_answer"
            queue_reason = "AI drafted rows, but at least one row still needs engineer confirmation."
        elif ai_review and related_rows:
            if all(str(row.get("review_status") or "").lower() in {"ready", "approved"} for row in related_rows):
                queue_status = "completed"
                queue_reason = "Final workbook rows are already ready or approved."
            else:
                queue_status = "ai_drafted"
                queue_reason = "AI already drafted this logic group; finish the final row review."
        else:
            queue_status = "ready_for_ai"
            queue_reason = "Definitions look sufficient for an AI rewrite of the final workbook rows."

        if queue_status == "needs_engineer_answer" and (note or attachments):
            queue_reason += " Added engineer context is available for the next AI run."

        queue_rows.append(
            {
                "logic_id": logic_id,
                "control_name": item.get("control_name", ""),
                "parse_status": item.get("parse_status", ""),
                "queue_status": queue_status,
                "queue_reason": queue_reason,
                "missing_terms": missing_terms,
                "row_count": len(related_rows),
                "row_statuses": dict(related_statuses),
                "has_engineer_note": bool(note),
                "attachment_count": len(attachments),
                "ai_summary": str(ai_review.get("summary") or ""),
                "run_candidate": queue_status in {"ready_for_ai", "needs_engineer_answer"},
            }
        )

    summary = Counter(str(row.get("queue_status") or "") for row in queue_rows)
    return {
        "logic_groups": queue_rows,
        "summary": {
            "total": len(queue_rows),
            "ready_for_ai": summary.get("ready_for_ai", 0),
            "blocked_missing_definition": summary.get("blocked_missing_definition", 0),
            "needs_engineer_answer": summary.get("needs_engineer_answer", 0),
            "ai_drafted": summary.get("ai_drafted", 0),
            "completed": summary.get("completed", 0),
            "no_rows": summary.get("no_rows", 0),
        },
        "run_logic_ids": [str(row.get("logic_id") or "") for row in queue_rows if row.get("run_candidate")],
    }


def paginate_workbook_rows(
    rows: list[dict[str, Any]],
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 0,
    issues_only: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filtered = list(rows)
    query = str(q or "").strip().lower()
    if query:
        filtered = [
            r
            for r in filtered
            if query in str(r.get("candidate_id") or "").lower()
            or query in str(r.get("event") or "").lower()
            or query in str(r.get("test_function") or "").lower()
            or query in str(r.get("use_case") or "").lower()
        ]
    if issues_only:
        filtered = [
            r
            for r in filtered
            if not (r.get("validation") or {}).get("ok", True)
            or (r.get("logic_compliance") or {}).get("logic_comply") in {"partial", "fail"}
        ]
    total = len(filtered)
    size = int(page_size or 0)
    if size <= 0:
        return filtered, {"page": 1, "page_size": total, "total": total, "pages": 1}
    page = max(1, int(page or 1))
    pages = max(1, (total + size - 1) // size)
    start = (page - 1) * size
    end = start + size
    return filtered[start:end], {
        "page": page,
        "page_size": size,
        "total": total,
        "pages": pages,
    }


def build_workbench_summary(bundle: dict[str, Any], *, language: str = "EN") -> dict[str, Any]:
    preview = build_customer_testspec_preview(bundle, language=language)
    evidence = build_evidence_graph(bundle)
    ai_queue = build_ai_queue(bundle, language=language)
    rows = preview["rows"]
    return {
        "rows_total": len(rows),
        "rows_ready": sum(1 for row in rows if str(row.get("review_status") or "").lower() in {"ready", "approved"}),
        "rows_blocked": sum(1 for row in rows if "blocked" in str(row.get("review_status") or "").lower()),
        "rows_needing_review": sum(
            1
            for row in rows
            if str(row.get("review_status") or "").lower() not in {"ready", "approved"}
            and "blocked" not in str(row.get("review_status") or "").lower()
        ),
        "missing_terms": evidence["summary"]["terms_missing_definition"],
        "logic_groups": len(bundle.get("logic_review_items") or []),
        "logic_groups_partial_or_failed": sum(
            1
            for item in bundle.get("logic_review_items") or []
            if str(item.get("parse_status") or "") != "ok"
        ),
        "ai_ready_groups": ai_queue["summary"]["ready_for_ai"],
        "ai_blocked_groups": ai_queue["summary"]["blocked_missing_definition"],
        "ai_waiting_groups": ai_queue["summary"]["needs_engineer_answer"],
    }
