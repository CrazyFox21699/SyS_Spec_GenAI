"""Brief readiness gate before Copy brief for Copilot."""

from __future__ import annotations

from typing import Any

from web.knowledge_validation import compliance_snapshot, failing_candidates
from web.m365_brief import BRIEF_CHAR_LIMIT, build_copilot_brief


def _logic_block(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    for lb in bundle.get("logic_blocks") or []:
        if lb.get("id") == logic_id:
            return lb
    return {}


def _logic_review_item(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    for row in bundle.get("logic_review_items") or []:
        if str(row.get("logic_id") or "") == logic_id:
            return row
    return {}


def _candidate_count(bundle: dict[str, Any], logic_id: str) -> int:
    n = 0
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") == logic_id:
            n += 1
    return n


def validate_brief_readiness(
    bundle: dict[str, Any],
    logic_id: str,
    engineer_note: str = "",
    *,
    brief_text: str | None = None,
) -> dict[str, Any]:
    """Score brief before engineer copies to Copilot. Blockers prevent copy."""
    blockers: list[str] = []
    warnings: list[str] = []

    lb = _logic_block(bundle, logic_id)
    item = _logic_review_item(bundle, logic_id)
    control = str(lb.get("name") or item.get("control_name") or logic_id)
    tc_count = _candidate_count(bundle, logic_id)

    if not lb and not item:
        blockers.append(f"Logic group `{logic_id}` not found in bundle.")
    if tc_count == 0:
        blockers.append("No test cases linked to this logic group — run Review specification first.")

    expression = str(
        lb.get("raw_expression") or lb.get("expression") or item.get("raw_expression") or item.get("expression") or ""
    ).strip()
    if not expression:
        blockers.append("Logic expression is empty — parser may have failed.")

    parse_status = str(item.get("parse_status") or lb.get("parse_status") or "unknown").lower()
    if parse_status == "failed":
        blockers.append("Parse status failed — align source table with tree before asking Copilot.")
    elif parse_status == "partial":
        warnings.append("Parse status partial — Copilot must cite source table rows, not invent AND/OR.")
    elif parse_status == "unknown" and expression:
        warnings.append("Parse status unknown — treat Copilot output as draft only.")

    note = (engineer_note or "").strip()
    if not note:
        warnings.append("Engineer note is empty — add signal meanings, ranges, or equalities before Copy brief.")

    unresolved = [str(x) for x in (lb.get("unresolved_refs") or []) if str(x).strip()]
    if unresolved:
        preview = ", ".join(unresolved[:8])
        suffix = "…" if len(unresolved) > 8 else ""
        warnings.append(f"Missing definitions ({len(unresolved)}): {preview}{suffix}")

    snapshot = compliance_snapshot(bundle, logic_id)
    fails = failing_candidates(snapshot)
    if snapshot and len(fails) == len(snapshot):
        warnings.append("All test cases fail logic_compliance — engineer note must explain each path intent.")
    elif fails:
        warnings.append(f"{len(fails)}/{len(snapshot)} test case(s) fail logic_compliance — Copilot should fix Given values.")

    open_issues = _open_issues_for_logic(bundle, logic_id, control)
    if open_issues:
        warnings.append(f"{len(open_issues)} open issue(s) for this control — see brief Issues section.")

    text = brief_text if brief_text is not None else build_copilot_brief(bundle, logic_id, note)
    byte_size = len(text.encode("utf-8"))
    if len(text) > BRIEF_CHAR_LIMIT:
        warnings.append(
            f"Brief is {len(text)} chars — Copilot prompt may truncate above {BRIEF_CHAR_LIMIT} chars."
        )

    return {
        "ok": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "logic_id": logic_id,
        "control_name": control,
        "test_case_count": tc_count,
        "parse_status": parse_status,
        "open_issue_count": len(open_issues),
        "compliance_fail_count": len(fails),
        "compliance_total": len(snapshot),
        "brief_char_size": len(text),
        "brief_byte_size": byte_size,
        "engineer_note_present": bool(note),
    }


def _open_issues_for_logic(bundle: dict[str, Any], logic_id: str, control_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = {logic_id, control_name}
    for issue in bundle.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        if issue.get("resolved_in_review"):
            continue
        sev = str(issue.get("display_severity") or issue.get("severity") or "").lower()
        if sev in ("ok", "info"):
            continue
        affected = {str(x) for x in issue.get("affected_items") or []}
        if affected & keys:
            out.append(issue)
    item = _logic_review_item(bundle, logic_id)
    for issue in item.get("issues") or []:
        if isinstance(issue, dict) and issue not in out:
            out.append(issue)
    return out[:20]
