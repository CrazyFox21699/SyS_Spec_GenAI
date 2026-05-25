"""Apply Copilot testcase drafts — full workbook fields, add_new, no-op detection."""

from __future__ import annotations

import re
from typing import Any

from src.exporters.customer_testspec_exporter import build_customer_testspec_preview
from web.candidate_mutations import allocate_candidate_id, sanitize_id, update_candidate_identity


_GIVEN_LINE = re.compile(r"(?im)^\s*Given:\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.+)$")


def _row_by_candidate(bundle: dict[str, Any], logic_id: str) -> dict[str, dict[str, Any]]:
    preview = build_customer_testspec_preview(bundle, language="EN")
    out: dict[str, dict[str, Any]] = {}
    for row in preview.get("rows") or []:
        cid = str(row.get("candidate_id") or "")
        if not cid:
            continue
        for cand in bundle.get("test_candidates") or []:
            if cand.get("id") == cid:
                if str((cand.get("traceability") or {}).get("logic_block") or "") == logic_id:
                    out[cid] = row
                break
    return out


def _parse_given_lines(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in str(text or "").splitlines():
        m = _GIVEN_LINE.match(line)
        if m:
            rows.append({"signal": m.group(1).upper(), "value": m.group(2).strip(), "operator": "=="})
    return rows


def _fields_identical(before: dict[str, str], after: dict[str, str]) -> bool:
    keys = ("use_case", "operation", "expected_input", "expected_output")
    return all(str(before.get(k) or "").strip() == str(after.get(k) or "").strip() for k in keys)


def build_full_row_diffs(
    bundle: dict[str, Any],
    logic_id: str,
    drafts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    before_rows = _row_by_candidate(bundle, logic_id)
    diffs: list[dict[str, Any]] = []
    for i, draft in enumerate(drafts):
        if not isinstance(draft, dict):
            continue
        cid = str(draft.get("candidate_id") or draft.get("proposed_id") or "")
        action = str(draft.get("action") or "update_existing")
        before = before_rows.get(cid) or {
            "use_case": "",
            "operation": "",
            "expected_input": "",
            "expected_output": "",
        }
        after = {
            "use_case": draft.get("use_case") or "",
            "operation": draft.get("operation") or "",
            "expected_input": draft.get("expected_input") or "",
            "expected_output": draft.get("expected_output") or "",
        }
        noop = action == "update_existing" and cid in before_rows and _fields_identical(before, after)
        diffs.append(
            {
                "draft_index": i,
                "candidate_id": cid,
                "action": action,
                "plan_item_id": draft.get("plan_item_id"),
                "before": before,
                "after": after,
                "noop": noop,
                "default_selected": not noop,
            }
        )
    return diffs


def preview_apply_drafts(
    bundle: dict[str, Any],
    logic_id: str,
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    diffs = build_full_row_diffs(bundle, logic_id, drafts)
    noop_count = sum(1 for d in diffs if d.get("noop"))
    return {
        "preview": True,
        "diffs": diffs,
        "draft_count": len(drafts),
        "noop_count": noop_count,
    }


def _apply_overlay(bundle: dict[str, Any], candidate_id: str, draft: dict[str, Any], *, logic_id: str) -> None:
    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    overlay = dict(overlays.get(candidate_id) or {})
    en = dict(overlay.get("en") or {})
    changed: set[str] = set(overlay.get("changed_fields") or [])
    field_map = {
        "use_case": draft.get("use_case"),
        "operation": draft.get("operation"),
        "expected_input": draft.get("expected_input"),
        "expected_output": draft.get("expected_output"),
    }
    label_map = {
        "use_case": "UseCase",
        "operation": "Operation",
        "expected_input": "ExpectedInput",
        "expected_output": "ExpectedOutput",
    }
    for key, val in field_map.items():
        if val is None:
            continue
        text = str(val).strip()
        if text:
            en[key] = text
            changed.add(label_map[key])
    overlay["en"] = en
    overlay["provider"] = "m365_copilot"
    overlay["logic_id"] = logic_id
    overlay["changed_fields"] = sorted(changed)
    overlays[candidate_id] = overlay


def _sync_given_from_input(cand: dict[str, Any], expected_input: str) -> None:
    rows = _parse_given_lines(expected_input)
    if not rows:
        return
    op = dict(cand.get("operation") or {})
    op["given"] = rows
    cand["operation"] = op


def _create_candidate_from_draft(
    bundle: dict[str, Any],
    logic_id: str,
    draft: dict[str, Any],
    *,
    control_name: str = "",
) -> dict[str, Any]:
    proposed = str(draft.get("proposed_id") or draft.get("candidate_id") or "").strip()
    if proposed:
        try:
            cid = sanitize_id(proposed, field="candidate_id")
        except ValueError:
            cid = allocate_candidate_id(bundle, prefix=f"{logic_id}_TC"[:12])
    else:
        cid = allocate_candidate_id(bundle, prefix=f"{logic_id}_TC"[:12])

    existing = {str(c.get("id") or "") for c in bundle.get("test_candidates") or []}
    if cid in existing:
        cid = allocate_candidate_id(bundle, prefix=f"{logic_id}_TC"[:12])

    cand = {
        "id": cid,
        "status": "candidate",
        "source": "m365_copilot",
        "test_function": draft.get("test_function") or control_name or "Copilot test case",
        "event": draft.get("event") or draft.get("plan_item_id") or "copilot_add",
        "use_case_description": draft.get("use_case") or "",
        "precondition": [],
        "operation": {"given": [], "when": []},
        "expectation": [],
        "traceability": {
            "logic_block": logic_id,
            "control_name": control_name,
            "source": "m365_copilot",
        },
        "confidence": draft.get("confidence") or "medium",
        "review_required": True,
        "review_status": "review_required",
    }
    _sync_given_from_input(cand, draft.get("expected_input") or "")
    bundle.setdefault("test_candidates", []).append(cand)
    _apply_overlay(bundle, cid, draft, logic_id=logic_id)
    return cand


def apply_draft_to_bundle(
    bundle: dict[str, Any],
    logic_id: str,
    draft: dict[str, Any],
    *,
    control_name: str = "",
) -> dict[str, Any]:
    action = str(draft.get("action") or "update_existing").strip().lower()
    cid = str(draft.get("candidate_id") or draft.get("proposed_id") or "")

    if action == "retire":
        for cand in bundle.get("test_candidates") or []:
            if cand.get("id") == cid:
                cand["status"] = "removed"
                return {"ok": True, "candidate_id": cid, "action": "retire"}
        return {"ok": False, "error": f"Candidate not found: {cid}"}

    if action == "add_new":
        cand = _create_candidate_from_draft(bundle, logic_id, draft, control_name=control_name)
        return {"ok": True, "candidate_id": cand.get("id"), "action": "add_new"}

    cand = next((c for c in bundle.get("test_candidates") or [] if c.get("id") == cid), None)
    if not cand:
        cand = _create_candidate_from_draft(bundle, logic_id, draft, control_name=control_name)
        return {"ok": True, "candidate_id": cand.get("id"), "action": "add_new"}

    if draft.get("use_case"):
        cand["use_case_description"] = draft.get("use_case")
    if draft.get("test_function"):
        cand["test_function"] = draft.get("test_function")
    if draft.get("event"):
        cand["event"] = draft.get("event")
    new_id = str(draft.get("new_candidate_id") or draft.get("proposed_id") or "").strip()
    if new_id and new_id != cid:
        try:
            out = update_candidate_identity(bundle, cid, new_candidate_id=new_id)
            cid = out["candidate_id"]
            cand = out["candidate"]
        except (ValueError, KeyError):
            pass
    _sync_given_from_input(cand, draft.get("expected_input") or "")
    _apply_overlay(bundle, cid, draft, logic_id=logic_id)
    cand["review_status"] = "review_required"
    return {"ok": True, "candidate_id": cid, "action": "update_existing"}


def confirm_apply_drafts(
    bundle: dict[str, Any],
    logic_id: str,
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    lb = next((b for b in bundle.get("logic_blocks") or [] if b.get("id") == logic_id), None)
    control = str((lb or {}).get("name") or logic_id)
    applied: list[dict[str, Any]] = []
    errors: list[str] = []
    for draft in drafts:
        if draft.get("noop"):
            continue
        out = apply_draft_to_bundle(bundle, logic_id, draft, control_name=control)
        if out.get("ok"):
            applied.append(out)
        else:
            errors.append(str(out.get("error") or "apply failed"))

    ai = bundle.setdefault("ai_assists", {})
    signal_updates = (get_copilot_plan(bundle, logic_id) or {}).get("signal_updates") or []
    eng = ai.setdefault("engineer_definitions", {})
    for row in signal_updates:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().upper()
        definition = str(row.get("definition") or "").strip()
        if name and definition:
            eng[name] = {
                "name": name,
                "definition": definition,
                "logic_id": logic_id,
                "source": "m365_copilot_plan",
            }

    return {
        "ok": bool(applied),
        "applied_count": len(applied),
        "applied": applied,
        "errors": errors,
        "candidates_updated": len([a for a in applied if a.get("action") == "update_existing"]),
        "candidates_added": len([a for a in applied if a.get("action") == "add_new"]),
    }


def get_copilot_plan(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    sessions = (bundle.get("ai_assists") or {}).get("copilot_sessions") or {}
    return dict((sessions.get(logic_id) or {}).get("plan") or {})
