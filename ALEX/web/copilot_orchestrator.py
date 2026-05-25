"""Orchestrate M365 Copilot context → plan → write workflow."""

from __future__ import annotations

from typing import Any

from web.copilot_context_pack import (
    build_context_pack,
    cache_context_pack,
    get_copilot_session,
    save_copilot_drafts,
    save_copilot_plan,
)
from web.copilot_planner import generate_plan_via_m365
from web.copilot_writer import (
    write_batch_size,
    write_drafts_via_m365,
    write_retry_for_plan_items,
    write_retry_limit,
)
from web.testcase_apply import build_full_row_diffs, preview_apply_drafts


def build_context(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    engineer_note: str = "",
    focus_term: str = "",
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pack = build_context_pack(
        bundle,
        logic_id,
        engineer_note=engineer_note,
        focus_term=focus_term,
        cfg=cfg,
    )
    cache_context_pack(bundle, logic_id, pack)
    return {"ok": True, "context_pack": pack, "logic_id": logic_id}


def run_plan(
    bundle: dict[str, Any],
    logic_id: str,
    cfg: dict[str, Any],
    *,
    engineer_note: str = "",
    focus_term: str = "",
) -> dict[str, Any]:
    session = get_copilot_session(bundle, logic_id)
    pack = session.get("context_pack")
    if not pack:
        built = build_context(
            bundle,
            logic_id,
            engineer_note=engineer_note,
            focus_term=focus_term,
            cfg=cfg,
        )
        pack = built.get("context_pack")
    if engineer_note.strip():
        pack = build_context_pack(
            bundle,
            logic_id,
            engineer_note=engineer_note,
            focus_term=focus_term,
            cfg=cfg,
        )
        cache_context_pack(bundle, logic_id, pack)

    out = generate_plan_via_m365(cfg, pack, engineer_note=engineer_note)
    if not out.get("ok"):
        return out
    plan = out.get("plan") or {}
    save_copilot_plan(bundle, logic_id, plan)
    return {"ok": True, "logic_id": logic_id, "plan": plan, "provider": "m365"}


def update_plan(bundle: dict[str, Any], logic_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    save_copilot_plan(bundle, logic_id, plan)
    return {"ok": True, "logic_id": logic_id, "plan": plan}


def _merge_retry_drafts(
    drafts: list[dict[str, Any]],
    retry_drafts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not retry_drafts:
        return drafts
    retry_by_pid = {
        str(d.get("plan_item_id") or ""): d for d in retry_drafts if d.get("plan_item_id")
    }
    result: list[dict[str, Any]] = []
    replaced: set[str] = set()
    for d in drafts:
        pid = str(d.get("plan_item_id") or "")
        if pid and pid in retry_by_pid:
            result.append(retry_by_pid[pid])
            replaced.add(pid)
        else:
            result.append(d)
    for pid, d in retry_by_pid.items():
        if pid not in replaced:
            result.append(d)
    return result


def _retry_noop_drafts(
    bundle: dict[str, Any],
    logic_id: str,
    cfg: dict[str, Any],
    *,
    pack: dict[str, Any],
    plan: dict[str, Any],
    drafts: list[dict[str, Any]],
    diffs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    retries = write_retry_limit(cfg)
    if retries < 1:
        return drafts, 0

    retry_count = 0
    current = list(drafts)
    for attempt in range(retries):
        preview = preview_apply_drafts(bundle, logic_id, current)
        noop_diffs = [d for d in (preview.get("diffs") or []) if d.get("noop")]
        if not noop_diffs:
            break

        plan_ids: list[str] = []
        notes: list[str] = []
        for diff in noop_diffs:
            idx = diff.get("draft_index")
            if idx is None or idx < 0 or idx >= len(current):
                continue
            draft = current[idx]
            pid = str(draft.get("plan_item_id") or "")
            cid = str(diff.get("candidate_id") or draft.get("candidate_id") or "")
            if pid:
                plan_ids.append(pid)
            notes.append(
                f"plan_item_id={pid or '?'} candidate_id={cid}: "
                "previous draft matched snapshot — change use_case and/or expected I/O per plan intent."
            )

        if not plan_ids:
            break

        retry_out = write_retry_for_plan_items(
            cfg,
            pack,
            plan,
            plan_ids,
            retry_notes=notes,
        )
        if not retry_out.get("ok"):
            break
        current = _merge_retry_drafts(current, retry_out.get("drafts") or [])
        retry_count += 1

    return current, retry_count


def run_write(bundle: dict[str, Any], logic_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    session = get_copilot_session(bundle, logic_id)
    pack = session.get("context_pack")
    plan = session.get("plan")
    if not pack:
        return {"ok": False, "error": "Build context first."}
    if not plan or not plan.get("plan_items"):
        return {"ok": False, "error": "Generate or save a plan first."}

    out = write_drafts_via_m365(cfg, pack, plan, batch_size=write_batch_size(cfg))
    if not out.get("ok") and not out.get("drafts"):
        return out

    drafts = out.get("drafts") or []
    retry_count = 0
    preview = preview_apply_drafts(bundle, logic_id, drafts)
    noop_before = preview.get("noop_count", 0)
    if noop_before and write_retry_limit(cfg) > 0:
        drafts, retry_count = _retry_noop_drafts(
            bundle,
            logic_id,
            cfg,
            pack=pack,
            plan=plan,
            drafts=drafts,
            diffs=preview.get("diffs") or [],
        )
        preview = preview_apply_drafts(bundle, logic_id, drafts)

    drafts_payload = {"drafts": drafts, "provider": "m365"}
    save_copilot_drafts(bundle, logic_id, drafts_payload)
    session = get_copilot_session(bundle, logic_id)
    session["draft_diffs"] = preview.get("diffs") or []
    bundle.setdefault("ai_assists", {}).setdefault("copilot_sessions", {})[logic_id] = session
    return {
        "ok": True,
        "logic_id": logic_id,
        "drafts": drafts_payload.get("drafts"),
        "diffs": preview.get("diffs"),
        "noop_count": preview.get("noop_count", 0),
        "noop_count_before_retry": noop_before,
        "retry_count": retry_count,
        "batch_count": out.get("batch_count", 1),
        "partial": out.get("partial", False),
        "provider": "m365",
    }


def run_apply_preview(bundle: dict[str, Any], logic_id: str) -> dict[str, Any]:
    session = get_copilot_session(bundle, logic_id)
    drafts = (session.get("drafts") or {}).get("drafts") or []
    if not drafts:
        return {"ok": False, "error": "No drafts to preview."}
    preview = preview_apply_drafts(bundle, logic_id, drafts)
    session["draft_diffs"] = preview.get("diffs") or []
    bundle.setdefault("ai_assists", {}).setdefault("copilot_sessions", {})[logic_id] = session
    return {"ok": True, "logic_id": logic_id, **preview}


def run_confirm(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    draft_indices: list[int],
) -> dict[str, Any]:
    from web.testcase_apply import confirm_apply_drafts

    session = get_copilot_session(bundle, logic_id)
    drafts = (session.get("drafts") or {}).get("drafts") or []
    if not drafts:
        return {"ok": False, "error": "No drafts to apply."}
    selected = [drafts[i] for i in draft_indices if 0 <= i < len(drafts)]
    if not selected:
        return {"ok": False, "error": "No drafts selected."}
    return confirm_apply_drafts(bundle, logic_id, selected)
