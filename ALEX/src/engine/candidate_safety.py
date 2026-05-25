"""Block test candidates when logic is not safely parsed."""

from __future__ import annotations

from typing import Any


def apply_candidate_safety(
    candidates: list[dict[str, Any]],
    logic_blocks: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    *,
    strict_mode: bool = True,
) -> list[dict[str, Any]]:
    """
    Mark candidates blocked when linked logic cannot be trusted.

    Does not delete candidates — sets status=blocked with reason for review.
    """
    unsafe_controls: set[str] = set()
    unsafe_ids: set[str] = set()

    for lb in logic_blocks:
        if lb.get("parse_status") in ("failed", "partial"):
            unsafe_controls.add(str(lb.get("name", "")))
            unsafe_ids.add(str(lb.get("id", "")))
        if not lb.get("can_generate_candidates", lb.get("parse_status") == "ok"):
            unsafe_controls.add(str(lb.get("name", "")))
            unsafe_ids.add(str(lb.get("id", "")))
        for ref in lb.get("unresolved_refs") or []:
            unsafe_controls.add(str(lb.get("name", "")))

    blocking_issue_types = {
        "condition_parse_failed",
        "unsupported_logic_format",
        "unresolved_condition",
        "logic_block_parse_failed",
        "ambiguous_indentation",
        "missing_reference_definition",
    }
    for iss in issues:
        if iss.get("severity") == "error" and iss.get("type") in blocking_issue_types:
            for aff in iss.get("affected_items") or []:
                unsafe_controls.add(str(aff))
        if strict_mode and not iss.get("can_export", True):
            for aff in iss.get("affected_items") or []:
                unsafe_controls.add(str(aff))

    for c in candidates:
        logic_path = str(c.get("logic_path", ""))
        blocked = False
        reason = ""
        for name in unsafe_controls:
            if name and name in logic_path:
                blocked = True
                reason = f"Logic for `{name}` is not safely parsed (blocked export)."
                break
        if c.get("derivation") == "not_branch" and strict_mode:
            c["review_required"] = True
        if blocked:
            c["status"] = "blocked"
            c["review_status"] = "blocked"
            c["block_reason"] = reason
            c["can_export"] = False
        else:
            c.setdefault("can_export", c.get("parse_status") != "failed")
    return candidates
