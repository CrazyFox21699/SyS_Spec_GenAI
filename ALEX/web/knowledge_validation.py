"""Provider-agnostic validation after knowledge patches are applied."""

from __future__ import annotations

from typing import Any, Callable

from src.engine.concrete_test_values import materialize_expected_input
from src.engine.engineer_rules import apply_given_patches_to_bundle, dedupe_logic_block_given
from src.engine.logic_compliance import check_logic_compliance


def _candidate_ids_for_logic(bundle: dict[str, Any], logic_id: str) -> list[str]:
    out: list[str] = []
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if cid:
            out.append(cid)
    return out


def compliance_snapshot(bundle: dict[str, Any], logic_id: str) -> list[dict[str, Any]]:
    """Per-candidate logic_compliance for a logic block."""
    rows: list[dict[str, Any]] = []
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        expected_input = materialize_expected_input(cand, bundle=bundle)
        comp = check_logic_compliance(cand, bundle, expected_input=expected_input)
        rows.append(
            {
                "candidate_id": cid,
                "logic_comply": comp.get("logic_comply"),
                "missing_signals": comp.get("missing_signals") or [],
                "misplaced_in_given": comp.get("misplaced_in_given") or [],
                "expected_signals": comp.get("expected_signals") or [],
                "path": str(trace.get("path_id") or trace.get("logic_branch") or ""),
            }
        )
    return rows


def failing_candidates(snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in snapshot if r.get("logic_comply") not in ("pass", None)]


def mark_review_required_for_failures(bundle: dict[str, Any], logic_id: str, snapshot: list[dict[str, Any]]) -> None:
    fail_ids = {r["candidate_id"] for r in failing_candidates(snapshot)}
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if cid in fail_ids:
            cand["review_status"] = "review_required"
            cand["review_required"] = True


def apply_patches_with_validation(
    bundle: dict[str, Any],
    logic_id: str,
    patches: list[dict[str, Any]],
    *,
    source: str,
    validation_retries: int = 1,
    retry_infer: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """
    Apply structured Given patches, run logic_compliance, optionally retry inference once.
    """
    updated = apply_given_patches_to_bundle(bundle, logic_id, patches, source=source)
    snapshot = compliance_snapshot(bundle, logic_id)
    failures = failing_candidates(snapshot)
    retries_used = 0

    while failures and retries_used < validation_retries and retry_infer:
        retries_used += 1
        retry_patches = retry_infer(failures)
        if not retry_patches:
            break
        updated += apply_given_patches_to_bundle(bundle, logic_id, retry_patches, source=source)
        snapshot = compliance_snapshot(bundle, logic_id)
        failures = failing_candidates(snapshot)

    mark_review_required_for_failures(bundle, logic_id, snapshot)
    return {
        "candidates_updated": updated,
        "compliance": snapshot,
        "failures_remaining": len(failures),
        "retries_used": retries_used,
    }


def dedupe_only(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    n = dedupe_logic_block_given(bundle, logic_id)
    snapshot = compliance_snapshot(bundle, logic_id)
    return {
        "candidates_updated": n,
        "compliance": snapshot,
        "failures_remaining": len(failing_candidates(snapshot)),
        "retries_used": 0,
    }
