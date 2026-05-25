"""M365 Copilot Phase 2 — write full workbook testcase fields from approved plan."""

from __future__ import annotations

import json
from typing import Any

from web.m365_copilot import run_copilot_chat

DEFAULT_WRITE_BATCH_SIZE = 6


def _parse_json_response(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def write_batch_size(cfg: dict[str, Any] | None) -> int:
    if not cfg:
        return DEFAULT_WRITE_BATCH_SIZE
    assist = cfg.get("assist") or {}
    return max(1, min(12, int(assist.get("copilot_write_batch_size", DEFAULT_WRITE_BATCH_SIZE))))


def write_retry_limit(cfg: dict[str, Any] | None) -> int:
    if not cfg:
        return 1
    assist = cfg.get("assist") or {}
    return max(0, min(3, int(assist.get("copilot_write_retries", assist.get("validation_retries", 1)))))


def chunk_plan_items(plan: dict[str, Any], batch_size: int) -> list[list[dict[str, Any]]]:
    items = [row for row in (plan.get("plan_items") or []) if isinstance(row, dict)]
    if not items:
        return []
    size = max(1, batch_size)
    return [items[i : i + size] for i in range(0, len(items), size)]


def _writer_prompt(
    context_pack: dict[str, Any],
    plan: dict[str, Any],
    *,
    retry_notes: list[str] | None = None,
) -> str:
    style = context_pack.get("style_reference") or {}
    template = style.get("template") or {}
    rules = template.get("rules") or []
    examples = template.get("examples") or {}
    golden = style.get("golden_rows") or []
    rules_text = "\n".join(f"- {r}" for r in rules)
    golden_text = json.dumps(golden[:3], ensure_ascii=False, indent=2) if golden else "[]"
    plan_json = json.dumps(plan, ensure_ascii=False)[:12000]
    snapshots = {
        row.get("candidate_id"): {
            "use_case": row.get("use_case"),
            "operation": row.get("operation"),
            "expected_input": row.get("expected_input"),
            "expected_output": row.get("expected_output"),
        }
        for row in (context_pack.get("testcases") or [])
    }
    snap_json = json.dumps(snapshots, ensure_ascii=False)[:8000]
    patterns = context_pack.get("project_memory", {}).get("verification_patterns") or []
    patterns_json = json.dumps(patterns[:5], ensure_ascii=False)[:2000]

    retry_block = ""
    if retry_notes:
        retry_block = (
            "\n\nRETRY — previous drafts were NO-OP (identical to snapshot). "
            "You MUST produce different use_case and/or expected I/O per plan intent:\n"
            + "\n".join(f"- {n}" for n in retry_notes[:8])
            + "\n"
        )

    return (
        "You are Microsoft 365 Copilot writing automotive test specification workbook rows for ALEX.\n"
        "Phase 2: WRITE full testcase fields from the APPROVED PLAN below.\n\n"
        "Rules:\n"
        f"{rules_text}\n\n"
        "Example expected_input format:\n"
        f"{examples.get('expected_input', '')}\n\n"
        "Example expected_output format:\n"
        f"{examples.get('expected_output', '')}\n\n"
        f"Golden samples from engineer:\n{golden_text}\n\n"
        f"Verification patterns (reuse Given/Then structure when matching):\n{patterns_json}\n\n"
        "IMPORTANT:\n"
        "- Each draft MUST reference a plan_item_id from the plan.\n"
        "- If plan requires change, output MUST differ from current snapshot for that candidate.\n"
        "- For add_new, set action=add_new and proposed_id from plan.\n"
        "- Use concrete Given:/Then: lines with signal=value.\n"
        "- Include test_function and event when plan supplies them.\n"
        f"{retry_block}\n"
        f"Current testcase snapshots:\n{snap_json}\n\n"
        f"Approved plan (this batch):\n{plan_json}\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "drafts": [\n'
        "    {\n"
        '      "plan_item_id": "P1",\n'
        '      "action": "update_existing|add_new|retire",\n'
        '      "candidate_id": "TC_xxx",\n'
        '      "proposed_id": "optional for add_new",\n'
        '      "test_function": "optional",\n'
        '      "event": "optional",\n'
        '      "use_case": "...",\n'
        '      "operation": "...",\n'
        '      "expected_input": "...",\n'
        '      "expected_output": "...",\n'
        '      "confidence": "medium",\n'
        '      "open_questions": [],\n'
        '      "evidence_refs": []\n'
        "    }\n"
        "  ]\n"
        "}"
    )


def normalize_drafts(parsed: dict[str, Any]) -> dict[str, Any]:
    drafts_in = parsed.get("drafts") or []
    drafts: list[dict[str, Any]] = []
    if not isinstance(drafts_in, list):
        drafts_in = []
    for row in drafts_in:
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "update_existing").strip().lower()
        drafts.append(
            {
                "plan_item_id": row.get("plan_item_id"),
                "action": action,
                "candidate_id": row.get("candidate_id") or row.get("proposed_id"),
                "proposed_id": row.get("proposed_id"),
                "test_function": str(row.get("test_function") or "").strip(),
                "event": str(row.get("event") or "").strip(),
                "use_case": str(row.get("use_case") or "").strip(),
                "operation": str(row.get("operation") or "").strip(),
                "expected_input": str(row.get("expected_input") or "").strip(),
                "expected_output": str(row.get("expected_output") or "").strip(),
                "confidence": row.get("confidence") or "medium",
                "open_questions": row.get("open_questions") or [],
                "evidence_refs": row.get("evidence_refs") or [],
            }
        )
    return {"drafts": drafts, "provider": "m365"}


def _write_plan_slice(
    cfg: dict[str, Any],
    context_pack: dict[str, Any],
    plan_slice: dict[str, Any],
    *,
    retry_notes: list[str] | None = None,
) -> dict[str, Any]:
    try:
        reply = run_copilot_chat(cfg, _writer_prompt(context_pack, plan_slice, retry_notes=retry_notes))
    except Exception as exc:
        return {"ok": False, "error": str(exc) or "M365 write request failed"}
    parsed = _parse_json_response(reply)
    if not parsed.get("drafts"):
        return {
            "ok": False,
            "error": "Could not parse drafts JSON from Copilot.",
            "raw": reply[:800],
        }
    return {"ok": True, **normalize_drafts(parsed)}


def write_drafts_via_m365(
    cfg: dict[str, Any],
    context_pack: dict[str, Any],
    plan: dict[str, Any],
    *,
    batch_size: int | None = None,
    retry_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Write drafts for all plan items, batched to stay within context limits."""
    size = batch_size or write_batch_size(cfg)
    chunks = chunk_plan_items(plan, size)
    if not chunks:
        return {"ok": False, "error": "Plan has no items to write."}

    all_drafts: list[dict[str, Any]] = []
    batch_count = 0
    for chunk in chunks:
        plan_slice = {
            "understanding_summary": plan.get("understanding_summary"),
            "plan_items": chunk,
        }
        out = _write_plan_slice(cfg, context_pack, plan_slice, retry_notes=retry_notes)
        if not out.get("ok"):
            if all_drafts:
                return {
                    "ok": True,
                    "drafts": all_drafts,
                    "provider": "m365",
                    "batch_count": batch_count,
                    "partial": True,
                    "error": out.get("error"),
                }
            return out
        all_drafts.extend(out.get("drafts") or [])
        batch_count += 1

    return {
        "ok": True,
        "drafts": all_drafts,
        "provider": "m365",
        "batch_count": batch_count,
    }


def write_retry_for_plan_items(
    cfg: dict[str, Any],
    context_pack: dict[str, Any],
    plan: dict[str, Any],
    plan_item_ids: list[str],
    *,
    retry_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Re-write specific plan items (e.g. after NO-OP detection)."""
    wanted = {str(x).strip() for x in plan_item_ids if str(x).strip()}
    if not wanted:
        return {"ok": False, "error": "No plan items to retry."}
    items = [
        row
        for row in (plan.get("plan_items") or [])
        if isinstance(row, dict) and str(row.get("plan_item_id") or "") in wanted
    ]
    if not items:
        return {"ok": False, "error": "Plan items not found for retry."}
    plan_slice = {"understanding_summary": plan.get("understanding_summary"), "plan_items": items}
    return _write_plan_slice(cfg, context_pack, plan_slice, retry_notes=retry_notes)
