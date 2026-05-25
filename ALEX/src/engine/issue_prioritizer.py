"""Prioritize review issues by export impact."""

from __future__ import annotations

from typing import Any

_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}
_TYPE_RANK = {
    "logic_block_parse_failed": 10,
    "condition_parse_failed": 20,
    "unsupported_logic_format": 25,
    "unresolved_condition": 30,
    "condition_partially_parsed": 35,
    "diagram_review_required": 40,
    "transition_review_required": 45,
}


def _issue_score(issue: dict[str, Any]) -> tuple[int, int, str]:
    sev = str(issue.get("severity") or "warning").lower()
    typ = str(issue.get("type") or issue.get("id") or "").lower()
    type_rank = _TYPE_RANK.get(typ, 60)
    sev_rank = _SEVERITY_RANK.get(sev, 3)
    msg = str(issue.get("message") or "")
    return (sev_rank, type_rank, msg)


def prioritize_issues(
    issues: list[dict[str, Any]],
    *,
    logic_items: list[dict[str, Any]] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return issues sorted by export-blocking impact."""
    logic_by_name = {str(i.get("control_name") or ""): i for i in logic_items or []}
    enriched: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        row = dict(issue)
        control = str(
            row.get("control")
            or row.get("logic_id")
            or (row.get("source") or {}).get("control")
            or ""
        )
        logic_item = logic_by_name.get(control) or {}
        row["priority_tier"] = "blocker" if row.get("severity") == "error" else "review"
        if logic_item.get("parse_status") in ("failed", "partial"):
            row["priority_tier"] = "blocker"
        row["priority_score"] = _issue_score(row)
        enriched.append(row)
    enriched.sort(key=lambda r: (r["priority_score"], str(r.get("control") or "")))
    out = []
    for i, row in enumerate(enriched[:limit]):
        clean = {k: v for k, v in row.items() if k != "priority_score"}
        clean["priority_rank"] = i + 1
        out.append(clean)
    return out


def build_overview_dashboard(
    bundle: dict[str, Any],
    capability: dict[str, Any],
) -> dict[str, Any]:
    """Compact spec overview for large jobs."""
    logic = capability.get("logic") or {}
    items = bundle.get("logic_review_items") or []
    issues = bundle.get("issues") or []
    understanding = bundle.get("spec_understanding") or {}
    prioritized = prioritize_issues(issues, logic_items=items, limit=12)
    return {
        "logic_groups_total": logic.get("groups_total", len(items)),
        "logic_groups_ok": logic.get("groups_ok", 0),
        "logic_groups_partial": logic.get("groups_partial", 0),
        "logic_groups_failed": logic.get("groups_failed", 0),
        "understanding_percent": understanding.get("overall", {}).get("understanding_percent"),
        "understanding_status": understanding.get("overall", {}).get("status"),
        "top_blockers": [i for i in prioritized if i.get("priority_tier") == "blocker"][:6],
        "top_review_items": [i for i in prioritized if i.get("priority_tier") != "blocker"][:4],
        "prioritized_issues": prioritized,
    }
