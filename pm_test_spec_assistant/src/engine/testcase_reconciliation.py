"""Build candidate reconciliation plans from AI patch proposals."""

from __future__ import annotations

from typing import Any


def _candidate_index(bundle: dict[str, Any], logic_id: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if cid:
            out[cid] = cand
    return out


def build_reconciliation_plan(
    bundle: dict[str, Any],
    logic_id: str,
    patches: list[dict[str, Any]],
    *,
    provider: str = "ai",
) -> dict[str, Any]:
    """
    Classify AI proposals before/alongside application.

    This is intentionally conservative: unknown candidate ids do not mutate existing rows;
    they become add_new or needs_review actions for future UI diff review.
    """
    by_id = _candidate_index(bundle, logic_id)
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for idx, patch in enumerate(patches or []):
        if not isinstance(patch, dict):
            continue
        requested = str(patch.get("action") or "").strip()
        cid = str(patch.get("candidate_id") or "").strip()
        given = patch.get("given") if isinstance(patch.get("given"), list) else []
        citations = patch.get("citations") if isinstance(patch.get("citations"), list) else []
        reason = str(patch.get("note") or patch.get("reason") or "").strip()

        if requested == "retire":
            action = "retire" if cid in by_id else "needs_review"
        elif cid and cid in by_id:
            action = "update_existing"
            seen.add(cid)
        elif not cid and given:
            action = "add_new"
        else:
            action = "needs_review"

        actions.append(
            {
                "action": action,
                "candidate_id": cid,
                "patch_index": idx,
                "provider": provider,
                "reason": reason,
                "given": given,
                "citations": citations,
                "review_required": action in {"add_new", "retire", "needs_review"} or not citations,
            }
        )

    untouched = [cid for cid in by_id if cid not in seen]
    return {
        "logic_id": logic_id,
        "provider": provider,
        "actions": actions,
        "summary": {
            "update_existing": sum(1 for a in actions if a["action"] == "update_existing"),
            "add_new": sum(1 for a in actions if a["action"] == "add_new"),
            "retire": sum(1 for a in actions if a["action"] == "retire"),
            "needs_review": sum(1 for a in actions if a["action"] == "needs_review"),
            "untouched_existing": len(untouched),
        },
        "untouched_candidate_ids": untouched,
    }
