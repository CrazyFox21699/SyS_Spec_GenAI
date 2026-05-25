"""Schema validation for Copilot / AI knowledge patches before apply."""

from __future__ import annotations

from typing import Any


def _candidate_ids_for_logic(bundle: dict[str, Any], logic_id: str) -> set[str]:
    out: set[str] = set()
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if cid:
            out.add(cid)
    return out


def _is_approved(cand: dict[str, Any]) -> bool:
    status = str(cand.get("review_status") or "").strip().lower()
    return status == "approved"


def _candidates_by_id(bundle: dict[str, Any], logic_id: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cand in bundle.get("test_candidates") or []:
        trace = cand.get("traceability") or {}
        if str(trace.get("logic_block") or "") != logic_id:
            continue
        cid = str(cand.get("id") or cand.get("candidate_id") or "").strip()
        if cid:
            out[cid] = cand
    return out


def validate_knowledge_patches(
    patches: list[dict[str, Any]],
    bundle: dict[str, Any],
    logic_id: str,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fail closed on structural errors before storing pending patches.

    Returns { ok, errors[], warnings[], valid_patches[] }.
    """
    errors: list[str] = []
    warnings: list[str] = []
    valid: list[dict[str, Any]] = []

    if not patches:
        errors.append("No patches in JSON — expected a candidates array.")
        return {"ok": False, "errors": errors, "warnings": warnings, "valid_patches": []}

    allowed_ids = _candidate_ids_for_logic(bundle, logic_id)
    by_id = _candidates_by_id(bundle, logic_id)
    seen_ids: set[str] = set()

    assist = (cfg or {}).get("assist") if isinstance((cfg or {}).get("assist"), dict) else {}
    knowledge_cfg = assist.get("knowledge") if isinstance(assist.get("knowledge"), dict) else {}
    block_approved = knowledge_cfg.get("block_approved_patches", True)

    for idx, patch in enumerate(patches):
        if not isinstance(patch, dict):
            errors.append(f"patches[{idx}]: must be an object.")
            continue

        cid = str(patch.get("candidate_id") or "").strip()
        if not cid:
            errors.append(f"patches[{idx}]: missing candidate_id.")
            continue
        if cid in seen_ids:
            errors.append(f"patches[{idx}]: duplicate candidate_id `{cid}`.")
            continue
        seen_ids.add(cid)

        if cid not in allowed_ids:
            errors.append(f"patches[{idx}]: unknown candidate_id `{cid}` for logic `{logic_id}`.")
            continue

        cand = by_id.get(cid) or {}
        if block_approved and _is_approved(cand):
            errors.append(
                f"patches[{idx}]: `{cid}` is approved/ready — reject or change status before AI patch."
            )
            continue

        given = patch.get("given")
        if not isinstance(given, list) or not given:
            errors.append(f"patches[{idx}] `{cid}`: given must be a non-empty array.")
            continue

        sigs: set[str] = set()
        row_errors = False
        for gidx, row in enumerate(given):
            if not isinstance(row, dict):
                errors.append(f"patches[{idx}] `{cid}` given[{gidx}]: must be an object.")
                row_errors = True
                continue
            sig = str(row.get("signal") or "").strip().upper()
            val = row.get("value")
            if not sig:
                errors.append(f"patches[{idx}] `{cid}` given[{gidx}]: missing signal.")
                row_errors = True
                continue
            if val is None or str(val).strip() == "":
                errors.append(f"patches[{idx}] `{cid}` given[{gidx}]: missing value for `{sig}`.")
                row_errors = True
                continue
            if sig in sigs:
                errors.append(f"patches[{idx}] `{cid}`: duplicate signal `{sig}` in given.")
                row_errors = True
                continue
            sigs.add(sig)

        if row_errors:
            continue

        valid.append(patch)

    if not errors and not valid:
        errors.append("No valid patches after validation.")

    return {
        "ok": not errors and bool(valid),
        "errors": errors,
        "warnings": warnings,
        "valid_patches": valid if not errors else [],
    }
