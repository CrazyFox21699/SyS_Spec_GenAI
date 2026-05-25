"""Build Excel-like traceability matrix rows."""

from __future__ import annotations

from typing import Any

from src.engine.logic_tree_renderer import flatten_ast_to_rows


def build_traceability_matrix(
    test_candidates: list[dict[str, Any]],
    logic_blocks: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    *,
    timing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    issue_by_item: dict[str, str] = {}
    for iss in issues or []:
        for a in iss.get("affected_items") or []:
            issue_by_item[str(a)] = iss.get("id", iss.get("type", ""))

    trace_n = 0
    for c in test_candidates:
        cid = c.get("id", "")
        trace = c.get("traceability") or {}
        logic_path = ""
        op = c.get("operation") or {}
        given = op.get("given") or []
        if isinstance(given, list) and given:
            logic_path = "; ".join(
                str(g.get("signal") or g.get("note") or g) for g in given[:6]
            )
        trace_n += 1
        rows.append(
            {
                "trace_id": f"TR_{trace_n:04d}",
                "test_candidate_id": cid,
                "signal_input": ", ".join(trace.get("signals") or []) if isinstance(trace.get("signals"), list) else "",
                "condition": (trace.get("conditions") or [""])[0] if isinstance(trace.get("conditions"), list) else "",
                "parent_condition_group": trace.get("transition", ""),
                "logic_operator": "",
                "state_transition": str(trace.get("states", "")),
                "output": ", ".join(trace.get("outputs") or []) if isinstance(trace.get("outputs"), list) else "",
                "constant_timing": "",
                "source_evidence": _format_source(trace.get("source_evidence")),
                "reason": "; ".join(c.get("why_recommended") or [])[:200],
                "confidence": c.get("confidence", "medium"),
                "review_status": c.get("review_status", "pending"),
                "issue_link": issue_by_item.get(cid, ""),
                "candidate_status": c.get("status", "candidate"),
            }
        )

    for lb in logic_blocks:
        tree_id = lb.get("id", lb.get("name", ""))
        for flat in flatten_ast_to_rows(tree_id, lb.get("tree") or {}):
            trace_n += 1
            rows.append(
                {
                    "trace_id": f"TR_{trace_n:04d}",
                    "test_candidate_id": "",
                    "signal_input": "",
                    "condition": flat.get("condition_name") or flat.get("raw_text"),
                    "parent_condition_group": lb.get("name", ""),
                    "logic_operator": flat.get("operator", ""),
                    "state_transition": "",
                    "output": "",
                    "constant_timing": "",
                    "source_evidence": _format_source([lb.get("source")]),
                    "reason": f"Logic block `{lb.get('name')}` depth {flat.get('depth')}",
                    "confidence": "medium",
                    "review_status": "pending",
                    "issue_link": issue_by_item.get(tree_id, ""),
                    "candidate_status": "logic_only",
                }
            )

    for tn in timing or []:
        trace_n += 1
        rows.append(
            {
                "trace_id": f"TR_{trace_n:04d}",
                "test_candidate_id": "",
                "signal_input": "",
                "condition": "",
                "parent_condition_group": "",
                "logic_operator": "",
                "state_transition": "",
                "output": "",
                "constant_timing": tn.get("interpreted_as") or tn.get("raw_text"),
                "source_evidence": _format_source([tn.get("source")]),
                "reason": "Timing constant",
                "confidence": tn.get("confidence", "medium"),
                "review_status": "pending" if tn.get("review_required") else "ok",
                "issue_link": "",
                "candidate_status": "timing",
            }
        )
    return rows


def build_logic_path_coverage(
    test_candidates: list[dict[str, Any]],
    logic_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in test_candidates:
        op = c.get("operation") or {}
        given_s = str(op.get("given", ""))
        rows.append(
            {
                "test_candidate_id": c.get("id"),
                "covered_logic_path": given_s[:300],
                "positive_negative": "positive" if "not" not in c.get("event", "").lower() else "negative",
                "or_branch": "OR" in given_s.upper(),
                "not_condition_covered": "NOT" in given_s.upper() or "not" in c.get("event", "").lower(),
                "timing_covered": "timing" in given_s.lower() or "ms" in given_s.lower(),
                "fallback_covered": "backup" in given_s.lower() or "fallback" in given_s.lower(),
                "missing_coverage": c.get("block_reason", "") or "",
                "review_status": c.get("review_status", "pending"),
            }
        )
    return rows


def _format_source(evidence: Any) -> str:
    if not evidence:
        return ""
    if isinstance(evidence, list):
        parts = []
        for e in evidence[:3]:
            if isinstance(e, dict):
                parts.append(
                    f"{e.get('file', '')} {e.get('table', e.get('sheet', ''))} row {e.get('row', e.get('row_hint', ''))}".strip()
                )
            else:
                parts.append(str(e))
        return " | ".join(parts)
    return str(evidence)
