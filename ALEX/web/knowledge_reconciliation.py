"""Pending knowledge-apply preview, diffs, and selective confirmation."""

from __future__ import annotations

import copy
from typing import Any

from src.engine.concrete_test_values import materialize_expected_input
from src.engine.engineer_rules import dedupe_given_by_signal, given_rows_from_patch
from src.engine.logic_compliance import check_logic_compliance
from src.engine.testcase_reconciliation import build_reconciliation_plan
from web.knowledge_patch_validation import validate_knowledge_patches
from web.knowledge_validation import apply_patches_with_validation, compliance_snapshot, failing_candidates


def _candidates_for_logic(bundle: dict[str, Any], logic_id: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if cid:
            out[cid] = cand
    return out


def snapshot_candidate_io(bundle: dict[str, Any], logic_id: str) -> dict[str, dict[str, str]]:
    """Capture materialized Expected input before patches apply."""
    snaps: dict[str, dict[str, str]] = {}
    for cid, cand in _candidates_for_logic(bundle, logic_id).items():
        snaps[cid] = {
            "expected_input": materialize_expected_input(cand, bundle=bundle),
        }
    return snaps


def _preview_expected_input(cand: dict[str, Any], patch: dict[str, Any]) -> str:
    op = copy.deepcopy(cand.get("operation") or {})
    rows = patch.get("given") if isinstance(patch.get("given"), list) else []
    from src.engine.engineer_rules import dedupe_given_by_signal, given_rows_from_patch

    existing = list(op.get("given") or [])
    patch_given = given_rows_from_patch(rows, source="preview")
    op["given"] = dedupe_given_by_signal(existing + patch_given)
    preview = dict(cand)
    preview["operation"] = op
    return materialize_expected_input(preview)


def _preview_candidate_with_patch(cand: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    preview = copy.deepcopy(cand)
    op = copy.deepcopy(cand.get("operation") or {})
    rows = patch.get("given") if isinstance(patch.get("given"), list) else []
    existing = list(op.get("given") or [])
    patch_given = given_rows_from_patch(rows, source="preview")
    op["given"] = dedupe_given_by_signal(existing + patch_given)
    preview["operation"] = op
    return preview


def _compliance_for_patch(
    bundle: dict[str, Any],
    logic_id: str,
    cand: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    preview = _preview_candidate_with_patch(cand, patch)
    expected_input = materialize_expected_input(preview, bundle=bundle)
    comp = check_logic_compliance(preview, bundle, expected_input=expected_input)
    return {
        "logic_comply": comp.get("logic_comply"),
        "missing_signals": comp.get("missing_signals") or [],
        "misplaced_in_given": comp.get("misplaced_in_given") or [],
        "expected_signals": comp.get("expected_signals") or [],
    }


def build_patch_diffs(
    bundle: dict[str, Any],
    logic_id: str,
    patches: list[dict[str, Any]],
    *,
    before_snapshots: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    before = before_snapshots or snapshot_candidate_io(bundle, logic_id)
    by_id = _candidates_for_logic(bundle, logic_id)
    diffs: list[dict[str, Any]] = []

    for idx, patch in enumerate(patches or []):
        if not isinstance(patch, dict):
            continue
        cid = str(patch.get("candidate_id") or "").strip()
        action = str(patch.get("action") or "").strip()
        before_in = before.get(cid, {}).get("expected_input", "") if cid else ""
        after_in = ""
        compliance: dict[str, Any] = {}
        if cid and cid in by_id:
            after_in = _preview_expected_input(by_id[cid], patch)
            compliance = _compliance_for_patch(bundle, logic_id, by_id[cid], patch)
        comply = compliance.get("logic_comply")
        schema_ok = bool(cid and cid in by_id and isinstance(patch.get("given"), list) and patch.get("given"))
        diffs.append(
            {
                "patch_index": idx,
                "candidate_id": cid,
                "action": action,
                "before_expected_input": before_in,
                "after_expected_input": after_in,
                "given": patch.get("given") if isinstance(patch.get("given"), list) else [],
                "reason": str(patch.get("note") or patch.get("reason") or "").strip(),
                "citations": patch.get("citations") if isinstance(patch.get("citations"), list) else [],
                "logic_comply": comply,
                "missing_signals": compliance.get("missing_signals") or [],
                "schema_ok": schema_ok,
                "default_selected": schema_ok and comply in ("pass", None),
            }
        )
    return diffs


def store_pending_knowledge_apply(
    bundle: dict[str, Any],
    logic_id: str,
    patches: list[dict[str, Any]],
    *,
    provider: str,
    source: str = "ai_preview",
    definition_updates: list[dict[str, Any]] | None = None,
    cfg: dict[str, Any] | None = None,
    schema_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store AI patches for engineer review without mutating candidates."""
    validation = schema_validation or validate_knowledge_patches(patches, bundle, logic_id, cfg)
    effective_patches = validation.get("valid_patches") or patches
    before = snapshot_candidate_io(bundle, logic_id)
    reconciliation = build_reconciliation_plan(bundle, logic_id, effective_patches, provider=provider)
    diffs = build_patch_diffs(bundle, logic_id, effective_patches, before_snapshots=before)
    ai = bundle.setdefault("ai_assists", {})
    ai.setdefault("knowledge_apply", {})[logic_id] = {
        "provider": provider,
        "source": source,
        "status": "pending",
        "patches": effective_patches[:80],
        "before_snapshots": before,
        "reconciliation": reconciliation,
        "diffs": diffs,
        "definition_updates": definition_updates or [],
        "schema_validation": {
            "ok": validation.get("ok"),
            "errors": validation.get("errors") or [],
            "warnings": validation.get("warnings") or [],
        },
        "candidates_updated": 0,
        "failures_remaining": len(
            [d for d in diffs if d.get("logic_comply") not in ("pass", None)]
        ),
    }
    return {
        "ok": True,
        "preview": True,
        "provider": provider,
        "pending_patches": len(effective_patches),
        "reconciliation": reconciliation,
        "diffs": diffs,
        "schema_validation": validation,
        "candidates_updated": 0,
        "failures_remaining": len(
            [d for d in diffs if d.get("logic_comply") not in ("pass", None)]
        ),
    }


def get_knowledge_apply_payload(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    ai = bundle.get("ai_assists") or {}
    entry = ai.get("knowledge_apply", {}).get(logic_id) or {}
    if not entry:
        return {"logic_id": logic_id, "status": "none", "reconciliation": None, "diffs": []}
    return {
        "logic_id": logic_id,
        "status": entry.get("status") or "unknown",
        "provider": entry.get("provider"),
        "reconciliation": entry.get("reconciliation"),
        "diffs": entry.get("diffs") or [],
        "patches": entry.get("patches") or [],
        "schema_validation": entry.get("schema_validation"),
        "candidates_updated": entry.get("candidates_updated", 0),
        "failures_remaining": entry.get("failures_remaining", 0),
    }


def reject_pending_knowledge(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    ai = bundle.setdefault("ai_assists", {})
    entry = ai.setdefault("knowledge_apply", {}).get(logic_id)
    if not entry:
        return {"ok": True, "logic_id": logic_id, "status": "none"}
    entry["status"] = "rejected"
    entry["patches"] = []
    entry["diffs"] = []
    entry["reconciliation"] = build_reconciliation_plan(bundle, logic_id, [], provider=str(entry.get("provider") or ""))
    return {"ok": True, "logic_id": logic_id, "status": "rejected"}


def confirm_pending_knowledge(
    bundle: dict[str, Any],
    logic_id: str,
    patch_indices: list[int],
    cfg: dict[str, Any],
    *,
    source: str | None = None,
) -> dict[str, Any]:
    ai = bundle.get("ai_assists") or {}
    entry = ai.get("knowledge_apply", {}).get(logic_id) or {}
    if entry.get("status") not in ("pending", None) and not entry.get("patches"):
        return {"ok": False, "error": "No pending patches to apply.", "candidates_updated": 0}

    all_patches = entry.get("patches") or []
    if not all_patches:
        return {"ok": False, "error": "No pending patches to apply.", "candidates_updated": 0}

    selected = set(int(i) for i in patch_indices)
    if not selected:
        selected = set(range(len(all_patches)))
    patches = [p for i, p in enumerate(all_patches) if i in selected and isinstance(p, dict)]

    apply_source = source or str(entry.get("source") or "knowledge_confirm")
    provider = str(entry.get("provider") or "ai")
    result = apply_patches_with_validation(
        bundle,
        logic_id,
        patches,
        source=apply_source,
        validation_retries=0,
    )
    reconciliation = build_reconciliation_plan(bundle, logic_id, patches, provider=provider)
    entry.update(
        {
            "status": "applied",
            "patches": patches[:80],
            "reconciliation": reconciliation,
            "diffs": build_patch_diffs(bundle, logic_id, patches),
            **result,
        }
    )
    snapshot = compliance_snapshot(bundle, logic_id)
    return {
        "ok": True,
        "provider": provider,
        "candidates_updated": result.get("candidates_updated", 0),
        "failures_remaining": result.get("failures_remaining", 0),
        "reconciliation": reconciliation,
        "compliance_failures": len(failing_candidates(snapshot)),
        "applied_patch_count": len(patches),
    }
