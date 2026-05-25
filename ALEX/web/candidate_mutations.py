"""Create, clone, and soft-delete test candidates."""

from __future__ import annotations

import copy
import re
from typing import Any

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def sanitize_id(value: str, *, field: str = "id") -> str:
    text = str(value or "").strip()
    if not text or ".." in text or not _SAFE_ID.match(text):
        raise ValueError(f"Invalid {field}: {value!r}")
    return text


def allocate_candidate_id(bundle: dict[str, Any], prefix: str = "TC_ENG") -> str:
    existing = {str(c.get("id") or "") for c in bundle.get("test_candidates") or []}
    n = 1
    while True:
        cid = f"{prefix}_{n:03d}"
        if cid not in existing:
            return cid
        n += 1


def _blank_candidate(
    cid: str,
    *,
    logic_id: str = "",
    control_name: str = "",
) -> dict[str, Any]:
    return {
        "id": cid,
        "status": "candidate",
        "source": "engineer_manual",
        "test_function": control_name or "Engineer test case",
        "event": "manual",
        "use_case_description": "",
        "precondition": [],
        "operation": {"given": [], "when": []},
        "expectation": [],
        "traceability": {
            "logic_id": logic_id,
            "control_name": control_name,
            "source": "engineer_manual",
        },
        "why_recommended": ["Added by engineer"],
        "confidence": "medium",
        "review_required": True,
        "review_status": "review_required",
    }


def create_blank_candidate(
    bundle: dict[str, Any],
    *,
    logic_id: str = "",
    control_name: str = "",
) -> dict[str, Any]:
    if logic_id:
        logic_id = sanitize_id(logic_id, field="logic_id")
    cid = allocate_candidate_id(bundle)
    cand = _blank_candidate(cid, logic_id=logic_id, control_name=control_name)
    bundle.setdefault("test_candidates", []).append(cand)
    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    overlays[cid] = {
        "provider": "engineer_review",
        "logic_id": logic_id,
        "control_name": control_name,
        "en": {
            "use_case": "",
            "operation": "",
            "expected_input": "",
            "expected_output": "",
        },
        "changed_fields": [],
    }
    return cand


def clone_candidate(
    bundle: dict[str, Any],
    source_candidate_id: str,
    *,
    logic_id: str = "",
) -> dict[str, Any]:
    source_candidate_id = sanitize_id(source_candidate_id, field="source_candidate_id")
    if logic_id:
        logic_id = sanitize_id(logic_id, field="logic_id")
    src = next(
        (c for c in bundle.get("test_candidates") or [] if c.get("id") == source_candidate_id),
        None,
    )
    if not src:
        raise KeyError(f"Candidate not found: {source_candidate_id}")
    if str(src.get("status") or "") == "removed":
        raise KeyError(f"Candidate is removed: {source_candidate_id}")

    cid = allocate_candidate_id(bundle)
    cand = copy.deepcopy(src)
    cand["id"] = cid
    cand["status"] = "candidate"
    cand["source"] = "engineer_clone"
    cand["parent_id"] = source_candidate_id
    cand["review_status"] = "review_required"
    cand["review_required"] = True
    event = str(cand.get("event") or "manual")
    if "(copy)" not in event:
        cand["event"] = f"{event} (copy)"

    trace = dict(cand.get("traceability") or {})
    trace["cloned_from"] = source_candidate_id
    if logic_id:
        trace["logic_id"] = logic_id
    cand["traceability"] = trace

    bundle.setdefault("test_candidates", []).append(cand)

    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    src_overlay = copy.deepcopy(overlays.get(source_candidate_id) or {})
    src_overlay["provider"] = "engineer_review"
    src_overlay["logic_id"] = logic_id or src_overlay.get("logic_id") or trace.get("logic_id", "")
    overlays[cid] = src_overlay
    return cand


def rename_candidate_references(
    bundle: dict[str, Any],
    old_id: str,
    new_id: str,
    *,
    gtest_state: dict[str, Any] | None = None,
) -> None:
    """Move overlays, gtest drafts, and copilot session refs after ID rename."""
    if old_id == new_id:
        return
    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    if old_id in overlays:
        overlays[new_id] = overlays.pop(old_id)

    for session in (ai.get("copilot_sessions") or {}).values():
        if not isinstance(session, dict):
            continue
        for draft in session.get("drafts") or []:
            if isinstance(draft, dict) and str(draft.get("candidate_id") or "") == old_id:
                draft["candidate_id"] = new_id
        for diff in session.get("draft_diffs") or []:
            if isinstance(diff, dict) and str(diff.get("candidate_id") or "") == old_id:
                diff["candidate_id"] = new_id
        plan = session.get("plan") or {}
        for item in plan.get("plan_items") or []:
            if isinstance(item, dict) and str(item.get("candidate_id") or "") == old_id:
                item["candidate_id"] = new_id

    if gtest_state is not None:
        drafts = dict(gtest_state.get("drafts") or {})
        if old_id in drafts:
            drafts[new_id] = drafts.pop(old_id)
            gtest_state["drafts"] = drafts


def update_candidate_identity(
    bundle: dict[str, Any],
    candidate_id: str,
    *,
    new_candidate_id: str | None = None,
    test_function: str | None = None,
    event: str | None = None,
    gtest_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update testcase identity fields; rename ID when new_candidate_id is supplied."""
    candidate_id = sanitize_id(candidate_id, field="candidate_id")
    cand = next((c for c in bundle.get("test_candidates") or [] if c.get("id") == candidate_id), None)
    if not cand:
        raise KeyError(f"Candidate not found: {candidate_id}")

    new_id = candidate_id
    if new_candidate_id is not None:
        new_id = sanitize_id(new_candidate_id, field="new_candidate_id")
        if new_id != candidate_id:
            existing = {str(c.get("id") or "") for c in bundle.get("test_candidates") or []}
            if new_id in existing:
                raise ValueError(f"Candidate id already exists: {new_id}")
            cand["id"] = new_id
            rename_candidate_references(bundle, candidate_id, new_id, gtest_state=gtest_state)

    if test_function is not None:
        cand["test_function"] = str(test_function).strip()
    if event is not None:
        cand["event"] = str(event).strip()

    cand["review_status"] = cand.get("review_status") or "review_required"
    return {"candidate": cand, "candidate_id": new_id, "renamed_from": candidate_id if new_id != candidate_id else None}


def soft_delete_candidate(bundle: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    candidate_id = sanitize_id(candidate_id, field="candidate_id")
    for cand in bundle.get("test_candidates") or []:
        if cand.get("id") != candidate_id:
            continue
        cand["status"] = "removed"
        cand["review_status"] = "blocked"
        cand["review_required"] = True
        cand["removed_by"] = "engineer_review"
        ai = bundle.setdefault("ai_assists", {})
        overlays = ai.setdefault("candidate_overlays", {})
        overlay = dict(overlays.get(candidate_id) or {})
        overlay["removed"] = True
        overlay["review_required"] = True
        overlay["provider"] = overlay.get("provider") or "engineer_review"
        overlays[candidate_id] = overlay
        return cand
    raise KeyError(f"Candidate not found: {candidate_id}")
