"""M365 Copilot Phase 1 — understand spec and produce testcase plan."""

from __future__ import annotations

import json
from typing import Any

from web.m365_copilot import run_copilot_chat


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


def _plan_prompt(context_pack: dict[str, Any], engineer_note: str) -> str:
    pack_json = json.dumps(context_pack, ensure_ascii=False)[:22000]
    style = context_pack.get("style_reference") or {}
    rules = (style.get("template") or {}).get("rules") or []
    rules_text = "\n".join(f"- {r}" for r in rules[:12])
    return (
        "You are Microsoft 365 Copilot assisting ALEX (automotive test-spec tool).\n"
        "Phase 1: UNDERSTAND the spec context and produce a TEST PLAN — do NOT write full testcase prose yet.\n\n"
        "Use the Context Pack JSON below. Respect path intents (satisfy vs violate), coverage_gaps, and signal roles.\n"
        "When engineer note adds ranges or constraints, plan concrete signal values per test case with rationale.\n"
        "Propose add_new when coverage_gaps show missing paths or boundary slots.\n\n"
        f"Style rules (for later write phase):\n{rules_text}\n\n"
        f"Engineer note:\n{engineer_note.strip() or '(none)'}\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "understanding_summary": "plain language summary",\n'
        '  "signal_updates": [{"name":"SIG","definition":"...","role":"guard_input"}],\n'
        '  "plan_items": [\n'
        "    {\n"
        '      "plan_item_id": "P1",\n'
        '      "action": "update_existing|add_new|retire",\n'
        '      "candidate_id": "TC_xxx or null for add_new",\n'
        '      "proposed_id": "for add_new only",\n'
        '      "path_id": "optional",\n'
        '      "intent": "satisfy|violate|boundary_below|boundary_above",\n'
        '      "signal_values": [{"signal":"SIG","value":"2","note":"in-range"}],\n'
        '      "rationale": "why this TC needs these values",\n'
        '      "evidence_refs": ["row 4", "path branch_1"]\n'
        "    }\n"
        "  ],\n"
        '  "open_questions": ["string"]\n'
        "}\n\n"
        f"Context Pack:\n{pack_json}"
    )


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    items = plan.get("plan_items") or []
    if not isinstance(items, list):
        items = []
    normalized: list[dict[str, Any]] = []
    for i, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        pid = str(row.get("plan_item_id") or f"P{i + 1}")
        action = str(row.get("action") or "update_existing").strip().lower()
        if action not in ("update_existing", "add_new", "retire"):
            action = "update_existing"
        normalized.append(
            {
                "plan_item_id": pid,
                "action": action,
                "candidate_id": row.get("candidate_id"),
                "proposed_id": row.get("proposed_id"),
                "path_id": row.get("path_id"),
                "intent": row.get("intent") or "satisfy",
                "signal_values": row.get("signal_values") or [],
                "rationale": row.get("rationale") or "",
                "evidence_refs": row.get("evidence_refs") or [],
            }
        )
    return {
        "understanding_summary": str(plan.get("understanding_summary") or ""),
        "signal_updates": plan.get("signal_updates") or [],
        "plan_items": normalized,
        "open_questions": plan.get("open_questions") or [],
        "provider": "m365",
    }


def generate_plan_via_m365(
    cfg: dict[str, Any],
    context_pack: dict[str, Any],
    *,
    engineer_note: str = "",
) -> dict[str, Any]:
    try:
        reply = run_copilot_chat(cfg, _plan_prompt(context_pack, engineer_note))
    except Exception as exc:
        return {"ok": False, "error": str(exc) or "M365 plan request failed"}
    parsed = _parse_json_response(reply)
    if not parsed.get("plan_items"):
        return {
            "ok": False,
            "error": "Could not parse plan JSON from Copilot.",
            "raw": reply[:800],
        }
    plan = normalize_plan(parsed)
    return {"ok": True, "plan": plan, "provider": "m365"}
