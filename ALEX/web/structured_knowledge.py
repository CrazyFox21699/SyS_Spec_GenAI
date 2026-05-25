"""Structured overlay API helpers and constraint compile pipeline."""

from __future__ import annotations

from typing import Any

from src.engine.constraint_compiler import compile_constraints_to_patches
from src.engine.structured_overlay import (
    accepted_constraints,
    get_overlay,
    normalize_constraint,
    set_overlay,
)


def _constraint_definition_text(constraint: dict[str, Any]) -> str:
    kind = constraint.get("kind")
    unit = str(constraint.get("unit") or "").strip()
    suffix = f" {unit}" if unit else ""
    if kind == "equality":
        return f"= {constraint.get('value')}{suffix}".strip()
    if kind == "range_inclusive":
        lo = constraint.get("min")
        hi = constraint.get("max")
        if lo is not None and hi is not None and lo == int(lo) and hi == int(hi):
            return f"range inclusive {int(lo)}–{int(hi)}{suffix}".strip()
        return f"range inclusive {lo}–{hi}{suffix}".strip()
    return str(constraint.get("note") or "structured constraint").strip()


def _auto_accept_draft_constraints(overlay: dict[str, Any]) -> int:
    accepted = 0
    for row in overlay.get("constraints") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("review_status") or "") == "draft":
            row["review_status"] = "accepted"
            accepted += 1
    return accepted


def sync_accepted_constraints_to_definitions(
    bundle: dict[str, Any],
    logic_id: str,
    overlay: dict[str, Any],
) -> int:
    """Write accepted structured constraints into engineer_definitions for inbox status."""
    constraints = accepted_constraints(overlay)
    if not constraints:
        return 0
    ai = bundle.setdefault("ai_assists", {})
    eng = ai.setdefault("engineer_definitions", {})
    updated = 0
    for constraint in constraints:
        signal = str(constraint.get("signal") or "").strip().upper()
        if not signal:
            continue
        eng[signal] = {
            "name": signal,
            "definition": _constraint_definition_text(constraint),
            "logic_id": logic_id,
            "source": "constraint_compiler",
        }
        updated += 1
    return updated
from src.engine.testcase_reconciliation import build_reconciliation_plan
from web.knowledge_validation import apply_patches_with_validation, compliance_snapshot, failing_candidates


def overlay_payload(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    overlay = get_overlay(bundle, logic_id)
    return {
        "logic_id": logic_id,
        "overlay": overlay,
        "accepted_count": len(accepted_constraints(overlay)),
        "diagram_links_count": len(overlay.get("diagram_links") or []),
    }


def save_constraints(
    bundle: dict[str, Any],
    logic_id: str,
    constraints: list[dict[str, Any]],
) -> dict[str, Any]:
    overlay = get_overlay(bundle, logic_id)
    normalized: list[dict[str, Any]] = []
    for raw in constraints:
        if not isinstance(raw, dict):
            continue
        normalized.append(normalize_constraint(raw))
    overlay["constraints"] = normalized
    set_overlay(bundle, logic_id, overlay)
    return overlay_payload(bundle, logic_id)


def compile_accepted_constraints(
    bundle: dict[str, Any],
    logic_id: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Apply deterministic constraint compiler; returns apply summary."""
    from web.ai_provider import validation_retries

    overlay = get_overlay(bundle, logic_id)
    auto_accepted = _auto_accept_draft_constraints(overlay)
    if auto_accepted:
        set_overlay(bundle, logic_id, overlay)
    patches = compile_constraints_to_patches(bundle, logic_id, overlay)
    if not patches:
        return {
            "ok": False,
            "provider": "constraint_compiler",
            "error": "No constraints to compile. Add a range or equality rule first.",
            "candidates_updated": 0,
            "definitions_updated": 0,
            "auto_accepted": auto_accepted,
        }

    definitions_updated = sync_accepted_constraints_to_definitions(bundle, logic_id, overlay)

    result = apply_patches_with_validation(
        bundle,
        logic_id,
        patches,
        source="constraint_compiler",
        validation_retries=0,
    )
    ai = bundle.setdefault("ai_assists", {})
    reconciliation = build_reconciliation_plan(bundle, logic_id, patches, provider="constraint_compiler")
    ai.setdefault("knowledge_apply", {})[logic_id] = {
        "provider": "constraint_compiler",
        "patches": patches[:40],
        "reconciliation": reconciliation,
        "constraints_used": len(accepted_constraints(overlay)),
        **result,
    }
    snapshot = compliance_snapshot(bundle, logic_id)
    return {
        "ok": True,
        "provider": "constraint_compiler",
        "candidates_updated": result.get("candidates_updated", 0),
        "definitions_updated": definitions_updated,
        "failures_remaining": result.get("failures_remaining", 0),
        "patches_count": len(patches),
        "constraints_used": len(accepted_constraints(overlay)),
        "compliance_failures": len(failing_candidates(snapshot)),
        "auto_accepted": auto_accepted,
    }
