"""Copilot row-level testcase assist — no logic tree / context pack required."""

from __future__ import annotations

import json
from typing import Any

from web.m365_copilot import run_copilot_chat_result
from web.testcase_apply import apply_draft_to_bundle, preview_apply_drafts


def _row_prompt(row: dict[str, Any], *, engineer_note: str = "") -> str:
    return (
        "You are Microsoft 365 Copilot improving one automotive test-spec row for ALEX.\n"
        "Improve UseCase, Operation, Expected input, and Expected output for clarity and testability.\n"
        "Rules:\n"
        "- Keep candidate_id, test_function, and event unchanged unless engineer note asks otherwise.\n"
        "- Expected input: line-oriented Given:/When:/Precondition: as in project style.\n"
        "- Expected output: line-oriented Then: assertions.\n"
        "- Do not invent signals not implied by the row.\n"
        f"Engineer note: {engineer_note[:1500]}\n\n"
        f"Current row:\n{json.dumps(row, ensure_ascii=False, indent=2)[:8000]}\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "candidate_id": "...",\n'
        '  "action": "update_existing",\n'
        '  "use_case": "...",\n'
        '  "operation": "...",\n'
        '  "expected_input": "...",\n'
        '  "expected_output": "...",\n'
        '  "confidence": "medium",\n'
        '  "open_questions": []\n'
        "}"
    )


def _parse_draft(text: str, row: dict[str, Any]) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    cid = str(parsed.get("candidate_id") or row.get("candidate_id") or "")
    if not cid:
        return None
    return {
        "plan_item_id": "ROW1",
        "action": str(parsed.get("action") or "update_existing"),
        "candidate_id": cid,
        "test_function": str(parsed.get("test_function") or row.get("test_function") or ""),
        "event": str(parsed.get("event") or row.get("event") or ""),
        "use_case": str(parsed.get("use_case") or row.get("use_case") or ""),
        "operation": str(parsed.get("operation") or row.get("operation") or ""),
        "expected_input": str(parsed.get("expected_input") or row.get("expected_input") or ""),
        "expected_output": str(parsed.get("expected_output") or row.get("expected_output") or ""),
        "confidence": parsed.get("confidence") or "medium",
        "open_questions": parsed.get("open_questions") or [],
    }


def write_from_row_via_copilot(
    cfg: dict[str, Any],
    row: dict[str, Any],
    *,
    engineer_note: str = "",
) -> dict[str, Any]:
    chat = run_copilot_chat_result(cfg, _row_prompt(row, engineer_note=engineer_note))
    if not chat.get("ok"):
        return chat
    reply = str(chat.get("reply") or "")
    draft = _parse_draft(reply, row)
    if not draft:
        return {
            "ok": False,
            "error": "Could not parse row draft JSON from Copilot.",
            "error_category": "m365_copilot_api",
            "raw_preview": reply[:500],
        }
    return {"ok": True, "draft": draft, "provider": "m365", "raw_preview": reply[:300]}


def preview_row_draft(
    bundle: dict[str, Any],
    row: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    logic_id = str(row.get("logic_id") or "")
    if not logic_id:
        for block in bundle.get("logic_blocks") or []:
            logic_id = str(block.get("id") or "")
            if logic_id:
                break
    if not logic_id:
        logic_id = "IMPORTED"
    preview = preview_apply_drafts(bundle, logic_id, [draft])
    return {"ok": True, "logic_id": logic_id, **preview}


def apply_row_draft(
    bundle: dict[str, Any],
    row: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    logic_id = str(row.get("logic_id") or "")
    if not logic_id:
        for block in bundle.get("logic_blocks") or []:
            logic_id = str(block.get("id") or "")
            if logic_id:
                break
    if not logic_id:
        logic_id = "IMPORTED"
    control = str(row.get("control_name") or row.get("test_function") or logic_id)
    out = apply_draft_to_bundle(bundle, logic_id, draft, control_name=control)
    return {"ok": bool(out.get("ok")), "logic_id": logic_id, **out}
