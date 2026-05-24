"""Propose selective test-case regen after understanding improves."""

from __future__ import annotations

from typing import Any


def build_path_regen_proposals(
    bundle: dict[str, Any],
    logic_id: str,
) -> dict[str, Any]:
    """Return add_new / retire patches for uncovered or stale paths."""
    from src.engine.path_tc_matrix import build_path_tc_matrix
    from src.engine.testcase_reconciliation import build_reconciliation_plan

    matrix = build_path_tc_matrix(bundle, logic_id)
    if not matrix.get("ok"):
        return {"ok": False, "reason": matrix.get("reason"), "logic_id": logic_id}

    control = str(matrix.get("control_name") or logic_id)
    existing_ids = {
        str(c.get("id") or "")
        for c in bundle.get("test_candidates") or []
        if (c.get("traceability") or {}).get("logic_block") == logic_id
    }
    patches: list[dict[str, Any]] = []

    for path in matrix.get("paths") or []:
        if path.get("coverage_status") != "missing":
            continue
        path_id = str(path.get("path_id") or "")
        label = str(path.get("label") or path_id)
        cid = f"{logic_id}_{path_id}".replace(" ", "_")[:64]
        if cid in existing_ids:
            continue
        given = []
        for item in path.get("given_template") or []:
            given.append(
                {
                    "signal": item.get("signal"),
                    "value": str(item.get("value") or "1"),
                    "role": "stimulus",
                }
            )
        if not given:
            for sig in path.get("signals") or []:
                given.append({"signal": sig, "value": "1", "role": "stimulus"})
        patches.append(
            {
                "action": "add_new",
                "candidate_id": cid,
                "given": given,
                "note": f"Proposed TC for uncovered path {label}",
                "path_coverage_intent": "satisfy",
                "citations": [
                    {
                        "kind": "logic_path",
                        "logic_id": logic_id,
                        "path_id": path_id,
                        "control": control,
                    }
                ],
                "coverage": {
                    "logic_id": logic_id,
                    "path_id": path_id,
                    "completeness": "proposed",
                    "footnote_branch": path.get("footnote_branch"),
                },
            }
        )

    plan = build_reconciliation_plan(bundle, logic_id, patches, provider="path_regen")
    bundle.setdefault("path_regen_proposals", {})[logic_id] = {
        "patches": patches,
        "reconciliation": plan,
    }
    return {
        "ok": True,
        "logic_id": logic_id,
        "proposed_count": len(patches),
        "patches": patches,
        "reconciliation": plan,
        "matrix_summary": matrix.get("summary"),
    }
