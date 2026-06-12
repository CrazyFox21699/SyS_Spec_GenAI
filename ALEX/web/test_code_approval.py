"""Engineer approval workflow for generated GTest drafts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _draft(gtest_state: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    cid = str(candidate_id or "").strip()
    if not cid:
        return None
    d = (gtest_state.get("drafts") or {}).get(cid)
    return d if isinstance(d, dict) else None


def approve_test_code_drafts(
    gtest_state: dict[str, Any],
    candidate_ids: list[str],
    *,
    only_saved: bool = True,
) -> dict[str, Any]:
    approved: list[str] = []
    skipped: list[dict[str, str]] = []
    for cid in candidate_ids:
        cid = str(cid or "").strip()
        if not cid:
            continue
        draft = _draft(gtest_state, cid)
        if not draft:
            skipped.append({"candidate_id": cid, "reason": "NO_DRAFT"})
            continue
        st = str(draft.get("code_status") or "").upper()
        if only_saved and st != "SAVED":
            skipped.append({"candidate_id": cid, "reason": st or "NOT_SAVED"})
            continue
        draft["engineer_approved"] = True
        draft["approved_at"] = _now_iso()
        draft["approval_status"] = "CONFIRMED"
        draft["exportable"] = True
        approved.append(cid)
    return {"ok": True, "approved": approved, "skipped": skipped, "approved_count": len(approved)}


def confirm_test_code_drafts(
    gtest_state: dict[str, Any],
    candidate_ids: list[str],
) -> dict[str, Any]:
    """User-driven confirm: sets approval_status=CONFIRMED, exportable=True regardless of code_status.

    Only skips when code is genuinely empty. Does not require code_status=SAVED so
    quality-warning drafts (NEEDS_REVIEW) are confirmed and become exportable.
    """
    confirmed: list[str] = []
    skipped_empty_code: list[str] = []
    skipped_no_draft: list[str] = []
    selected_count = len([c for c in candidate_ids if str(c or "").strip()])
    for cid in candidate_ids:
        cid = str(cid or "").strip()
        if not cid:
            continue
        draft = _draft(gtest_state, cid)
        if not draft:
            skipped_no_draft.append(cid)
            continue
        full = str(draft.get("full_snippet") or draft.get("code_body") or "").strip()
        if not full:
            skipped_empty_code.append(cid)
            continue
        draft["engineer_approved"] = True
        draft["approved_at"] = _now_iso()
        draft["approval_status"] = "CONFIRMED"
        draft["exportable"] = True
        confirmed.append(cid)
    return {
        "ok": True,
        "confirmed": confirmed,
        "confirmed_count": len(confirmed),
        "skipped_empty_code": skipped_empty_code,
        "skipped_no_draft": skipped_no_draft,
        "selected_count": selected_count,
    }


def approve_all_saved_test_code(gtest_state: dict[str, Any]) -> dict[str, Any]:
    ids = [
        str(cid)
        for cid, d in (gtest_state.get("drafts") or {}).items()
        if isinstance(d, dict) and str(d.get("code_status") or "").upper() == "SAVED"
    ]
    return approve_test_code_drafts(gtest_state, ids, only_saved=True)


def mark_test_code_reviewed(
    gtest_state: dict[str, Any],
    candidate_ids: list[str],
) -> dict[str, Any]:
    marked: list[str] = []
    skipped: list[dict[str, str]] = []
    for cid in candidate_ids:
        cid = str(cid or "").strip()
        draft = _draft(gtest_state, cid)
        if not draft:
            skipped.append({"candidate_id": cid, "reason": "NO_DRAFT"})
            continue
        st = str(draft.get("code_status") or "").upper()
        if st not in ("NEEDS_REVIEW", "SAVED"):
            skipped.append({"candidate_id": cid, "reason": st or "NOT_REVIEWABLE"})
            continue
        draft["engineer_reviewed"] = True
        draft["reviewed_at"] = _now_iso()
        marked.append(cid)
    return {"ok": True, "marked": marked, "skipped": skipped, "marked_count": len(marked)}


def reopen_test_code_drafts(
    gtest_state: dict[str, Any],
    candidate_ids: list[str],
) -> dict[str, Any]:
    reopened: list[str] = []
    for cid in candidate_ids:
        cid = str(cid or "").strip()
        draft = _draft(gtest_state, cid)
        if not draft:
            continue
        draft.pop("engineer_approved", None)
        draft.pop("approved_at", None)
        draft.pop("engineer_reviewed", None)
        draft.pop("reviewed_at", None)
        draft.pop("approval_status", None)
        draft.pop("exportable", None)
        reopened.append(cid)
    return {"ok": True, "reopened": reopened, "reopened_count": len(reopened)}


def count_workflow_statuses(gtest_state: dict[str, Any]) -> dict[str, int]:
    drafts = gtest_state.get("drafts") or {}
    counts = {"SAVED": 0, "NEEDS_REVIEW": 0, "ERROR": 0, "NO_CODE": 0, "APPROVED": 0}
    for d in drafts.values():
        if not isinstance(d, dict):
            continue
        st = str(d.get("code_status") or "").upper()
        if not str(d.get("full_snippet") or d.get("code_body") or "").strip():
            counts["NO_CODE"] += 1
            continue
        if st == "SAVED":
            counts["SAVED"] += 1
            if d.get("engineer_approved"):
                counts["APPROVED"] += 1
        elif st == "NEEDS_REVIEW":
            counts["NEEDS_REVIEW"] += 1
        elif st == "ERROR":
            counts["ERROR"] += 1
    return counts
