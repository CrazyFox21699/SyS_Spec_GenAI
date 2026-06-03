"""GTest workspace helpers — load/save drafts, generate snippets, library presets."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from src.engine.concrete_test_values import materialize_expected_input, materialize_expected_output
from src.engine.gtest_codegen import (
    GTestHarnessConfig,
    build_gtest_skeleton,
    compose_full_translation_unit,
    default_harness_from_config,
    suggest_variable_map,
)
from src.engine.path_tc_matrix import _candidate_logic_id
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview
from src.importers.customer_testspec_importer import (
    build_structured_io,
    compute_body_hash,
    compute_spec_hash,
    structured_io_from_overlay,
)
from web.alex_storage import (
    code_style_samples_path,
    default_library_root,
    ensure_alex_data_dir,
    gtest_preset_path,
    migrate_legacy_alex_data,
    project_memory_path,
)
from web.code_style_samples import load_code_style_samples
from web.code_text_transform import delete_drafts, merge_drafts_to_monolith, wrap_draft_markers

GTEST_ARTIFACT = "gtest.json"
_PREVIEW_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_PREVIEW_CACHE_TTL_S = 45.0


def _cached_workbench_preview(
    bundle: dict[str, Any],
    *,
    job_id: str = "",
    bundle_version: int = 0,
    language: str = "EN",
) -> dict[str, Any]:
    key = f"{job_id}:{bundle_version}:{language}"
    hit = _PREVIEW_CACHE.get(key)
    if hit and monotonic() - hit[0] < _PREVIEW_CACHE_TTL_S:
        return hit[1]
    preview = build_customer_testspec_preview(bundle, language=language)
    _PREVIEW_CACHE[key] = (monotonic(), preview)
    if len(_PREVIEW_CACHE) > 32:
        oldest = min(_PREVIEW_CACHE.items(), key=lambda item: item[1][0])[0]
        _PREVIEW_CACHE.pop(oldest, None)
    return preview


def gtest_store_path(job_output: Path) -> Path:
    return job_output / "bundle" / GTEST_ARTIFACT


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_gtest_state(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    harness = default_harness_from_config(cfg)
    return {
        "harness": harness.to_dict(),
        "code_variable_map": {},
        "drafts": {},
        "tc_code_index": {},
        "updated_at": _now_iso(),
    }


def load_gtest_state(job_output: Path, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    path = gtest_store_path(job_output)
    if not path.exists():
        return default_gtest_state(cfg)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_gtest_state(cfg)
    base = default_gtest_state(cfg)
    base["harness"] = {**base["harness"], **(data.get("harness") or {})}
    base["code_variable_map"] = dict(data.get("code_variable_map") or {})
    base["drafts"] = dict(data.get("drafts") or {})
    base["tc_code_index"] = dict(data.get("tc_code_index") or {})
    base["mapping_coverage"] = dict(data.get("mapping_coverage") or {})
    base["project_code_config_meta"] = dict(data.get("project_code_config_meta") or {})
    base["updated_at"] = data.get("updated_at") or base["updated_at"]
    checkpoint = dict(data.get("copilot_batch_run_checkpoint") or {})
    if checkpoint:
        base.setdefault("copilot_batch", {})["run_checkpoint"] = checkpoint
    return base


def save_gtest_state(job_output: Path, state: dict[str, Any]) -> None:
    path = gtest_store_path(job_output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "harness": state.get("harness") or {},
        "code_variable_map": state.get("code_variable_map") or {},
        "drafts": state.get("drafts") or {},
        "tc_code_index": state.get("tc_code_index") or {},
        "mapping_coverage": state.get("mapping_coverage") or {},
        "project_code_config_meta": state.get("project_code_config_meta") or {},
        "updated_at": _now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def flush_batch_run_checkpoint(job_output: Path, state: dict[str, Any]) -> None:
    """Persist drafts + batch run state after each API chunk for crash recovery.

    Writes the same fields as save_gtest_state plus a 'copilot_batch_run_checkpoint'
    snapshot so a restart can skip already-SAVED testcases.
    """
    path = gtest_store_path(job_output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "harness": state.get("harness") or {},
        "code_variable_map": state.get("code_variable_map") or {},
        "drafts": state.get("drafts") or {},
        "tc_code_index": state.get("tc_code_index") or {},
        "mapping_coverage": state.get("mapping_coverage") or {},
        "project_code_config_meta": state.get("project_code_config_meta") or {},
        "copilot_batch_run_checkpoint": (state.get("copilot_batch") or {}).get("run") or {},
        "updated_at": _now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sync_gtest_to_bundle(bundle: dict[str, Any], gtest_state: dict[str, Any]) -> dict[str, Any]:
    ai = dict(bundle.get("ai_assists") or {})
    ai["gtest_harness"] = gtest_state.get("harness") or {}
    ai["code_variable_map"] = gtest_state.get("code_variable_map") or {}
    ai["gtest_drafts"] = gtest_state.get("drafts") or {}
    bundle["ai_assists"] = ai
    return bundle


def _logic_block_by_id(bundle: dict[str, Any], logic_id: str) -> dict[str, Any] | None:
    for block in bundle.get("logic_blocks") or []:
        if str(block.get("logic_id") or "") == logic_id:
            return block
    for block in bundle.get("resolved_logic_blocks") or []:
        if str(block.get("logic_id") or "") == logic_id:
            return block
    return None


def _candidate_by_id(bundle: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    for row in bundle.get("test_candidates") or []:
        if str(row.get("id") or "") == candidate_id:
            return row
    return None


def _definition_lookup(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for row in bundle.get("condition_definitions") or []:
        name = str(row.get("name") or "").strip()
        if name:
            lookup.setdefault(name, []).append(row)
    for row in bundle.get("signals") or []:
        name = str(row.get("name") or "").strip()
        if name:
            lookup.setdefault(name, []).append(row)
    return lookup


def collect_signal_names(bundle: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for sig in bundle.get("signals") or []:
        name = str(sig.get("name") or "").strip()
        if name:
            names.add(name)
    for cand in bundle.get("test_candidates") or []:
        for item in (cand.get("operation") or {}).get("given") or []:
            if isinstance(item, dict) and item.get("signal"):
                names.add(str(item["signal"]))
        for item in cand.get("expectation") or []:
            if isinstance(item, dict) and item.get("signal"):
                names.add(str(item["signal"]))
    return sorted(names)


def _overlay_for_candidate(bundle: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    ai = bundle.get("ai_assists") or {}
    return dict((ai.get("candidate_overlays") or {}).get(candidate_id) or {})


def _structured_io_for_candidate(
    bundle: dict[str, Any],
    candidate_id: str,
    *,
    language: str = "EN",
) -> dict[str, Any]:
    overlay = _overlay_for_candidate(bundle, candidate_id)
    if overlay.get("structured_io"):
        return dict(overlay["structured_io"])
    wb = _workbench_row_for_candidate(bundle, candidate_id, language=language)
    if wb:
        return build_structured_io(
            no=str(wb.get("no") or overlay.get("no") or ""),
            operation=str(wb.get("operation") or ""),
            expected_input=str(wb.get("expected_input") or ""),
            expected_output=str(wb.get("expected_output") or ""),
            remarks=str(overlay.get("remarks") or ""),
        )
    return structured_io_from_overlay(overlay, lang=language)


def classify_sync_status(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    language: str = "EN",
) -> dict[str, Any]:
    drafts = gtest_state.get("drafts") or {}
    candidate_ids = {str(c.get("id") or "") for c in (bundle.get("test_candidates") or []) if c.get("id")}
    rows: list[dict[str, Any]] = []
    summary: dict[str, int] = {"ok": 0, "no_code": 0, "stale_comment": 0, "stale_body": 0, "orphan_code": 0}

    for cid in sorted(candidate_ids):
        structured = _structured_io_for_candidate(bundle, cid, language=language)
        current_spec = compute_spec_hash(structured)
        current_body = compute_body_hash(structured)
        draft = drafts.get(cid) or {}
        if not (draft.get("full_snippet") or draft.get("code_body")):
            status = "no_code"
        elif str(draft.get("spec_hash") or "") == current_spec:
            status = "ok"
        elif str(draft.get("body_hash") or "") == current_body and draft.get("body_hash"):
            status = "stale_comment"
        else:
            status = "stale_body"
        summary[status] = summary.get(status, 0) + 1
        rows.append(
            {
                "candidate_id": cid,
                "status": status,
                "spec_hash": current_spec,
                "body_hash": current_body,
                "draft_spec_hash": draft.get("spec_hash"),
                "draft_body_hash": draft.get("body_hash"),
            }
        )

    for cid in sorted(set(drafts.keys()) - candidate_ids):
        summary["orphan_code"] += 1
        rows.append({"candidate_id": cid, "status": "orphan_code"})

    return {"ok": True, "summary": summary, "rows": rows}


def regen_comment_only_draft(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    candidate_id: str,
    *,
    language: str = "EN",
) -> dict[str, Any]:
    from src.engine.gtest_codegen import _build_spec_comments

    cid = str(candidate_id or "").strip()
    if not cid:
        return {"ok": False, "error": "candidate_id required"}
    draft = dict((gtest_state.get("drafts") or {}).get(cid) or {})
    code_body = str(draft.get("code_body") or "").strip()
    full = str(draft.get("full_snippet") or "").strip()
    if not code_body and full:
        idx = full.find("TEST_F(")
        if idx >= 0:
            code_body = full[idx:].strip()
            end_marker = f"// @alex:end {cid}"
            if end_marker in code_body:
                code_body = code_body[: code_body.rfind(end_marker)].strip()
    if not code_body and not full:
        return {"ok": False, "error": f"No saved code for {cid}"}

    structured = _structured_io_for_candidate(bundle, cid, language=language)
    candidate = _candidate_by_id(bundle, cid)
    logic_block = None
    if candidate:
        lid = _candidate_logic_id(candidate)
        if lid:
            logic_block = _logic_block_by_id(bundle, lid)
    given_when = "\n".join((structured.get("given_lines") or []) + (structured.get("when_lines") or []))
    then_text = "\n".join(structured.get("then_lines") or [])
    spec_block = _build_spec_comments(
        candidate=candidate,
        logic_block=logic_block,
        given_when_text=given_when,
        then_text=then_text,
    )
    if structured.get("operation"):
        spec_block = f"// Operation: {structured['operation'][:500]}\n{spec_block}".strip()
    if structured.get("remarks"):
        spec_block = f"{spec_block}\n// Remarks: {structured['remarks']}".strip()

    spec_hash = compute_spec_hash(structured)
    body_hash = compute_body_hash(structured)
    updated = wrap_draft_markers(
        cid,
        {
            "spec_comment_block": spec_block,
            "code_body": code_body,
            "spec_hash": spec_hash,
            "body_hash": body_hash,
            "source_kind": "regen_comment",
        },
        spec_hash=spec_hash,
    )
    updated["body_hash"] = body_hash
    save_draft(gtest_state, draft_key=cid, draft=updated, engineer_edited=False)
    return {"ok": True, "candidate_id": cid, "draft": updated}


def bulk_regen_comments(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    candidate_ids: list[str],
    *,
    language: str = "EN",
    stale_only: bool = False,
) -> dict[str, Any]:
    targets = list(candidate_ids)
    if stale_only:
        sync = classify_sync_status(bundle, gtest_state, language=language)
        targets = [r["candidate_id"] for r in sync.get("rows") or [] if r.get("status") == "stale_comment"]
    results: list[dict[str, Any]] = []
    ok_count = 0
    for cid in targets:
        one = regen_comment_only_draft(bundle, gtest_state, cid, language=language)
        results.append(one)
        if one.get("ok"):
            ok_count += 1
    return {"ok": True, "regenerated": ok_count, "results": results}


def bulk_delete_code(gtest_state: dict[str, Any], candidate_ids: list[str]) -> dict[str, Any]:
    return delete_drafts(gtest_state, candidate_ids)


def _workbench_row_for_candidate(
    bundle: dict[str, Any],
    candidate_id: str | None,
    *,
    language: str = "EN",
) -> dict[str, Any] | None:
    if not candidate_id:
        return None
    preview = build_customer_testspec_preview(bundle, language=language)
    for row in preview.get("rows") or []:
        if str(row.get("candidate_id") or "") == candidate_id:
            return row
    return None


def build_workspace_payload(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    language: str = "EN",
    job_id: str = "",
    bundle_version: int = 0,
    include_signals: bool = False,
) -> dict[str, Any]:
    harness = GTestHarnessConfig.from_dict(gtest_state.get("harness"))
    variable_map = dict(gtest_state.get("code_variable_map") or {})
    preview = _cached_workbench_preview(
        bundle,
        job_id=job_id,
        bundle_version=bundle_version,
        language=language,
    )
    logic_items = []
    seen: set[str] = set()
    for block in bundle.get("logic_blocks") or []:
        lid = str(block.get("logic_id") or "")
        if lid and lid not in seen:
            seen.add(lid)
            logic_items.append(
                {
                    "logic_id": lid,
                    "control_name": block.get("control_name", ""),
                    "expression": block.get("raw_expression") or block.get("expression") or "",
                }
            )
    payload: dict[str, Any] = {
        "harness": harness.to_dict(),
        "code_variable_map": variable_map,
        "drafts": gtest_state.get("drafts") or {},
        "tc_code_index": gtest_state.get("tc_code_index") or {},
        "code_style_samples": load_code_style_samples(bundle),
        "copilot_batch": gtest_state.get("copilot_batch") or {},
        "mapping_coverage": gtest_state.get("mapping_coverage") or {},
        "smart_workflow_run_report": gtest_state.get("smart_workflow_run_report") or {},
        "code_exemplar": gtest_state.get("code_exemplar") or {},
        "exemplar_batch": gtest_state.get("exemplar_batch") or {},
        "project_code_config_meta": gtest_state.get("project_code_config_meta") or {},
        "logic_items": logic_items,
        "workbench_rows": preview.get("rows") or [],
        "code_references": bundle.get("code_references") or [],
    }
    if include_signals:
        payload["signals"] = collect_signal_names(bundle)
    return payload


def generate_draft_for_request(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str | None = None,
    logic_id: str | None = None,
    variable_map: dict[str, str] | None = None,
    language: str = "EN",
) -> dict[str, Any]:
    harness = GTestHarnessConfig.from_dict(gtest_state.get("harness"))
    vmap = dict(gtest_state.get("code_variable_map") or {})
    if variable_map:
        vmap.update(variable_map)

    candidate = _candidate_by_id(bundle, candidate_id) if candidate_id else None
    logic_block = None
    if logic_id:
        logic_block = _logic_block_by_id(bundle, logic_id)
    elif candidate:
        lid = _candidate_logic_id(candidate)
        if lid:
            logic_block = _logic_block_by_id(bundle, lid)

    wb_row = _workbench_row_for_candidate(bundle, candidate_id, language=language)
    given_override = str(wb_row.get("expected_input") or "").strip() if wb_row else None
    then_override = str(wb_row.get("expected_output") or "").strip() if wb_row else None

    draft = build_gtest_skeleton(
        candidate=candidate,
        logic_block=logic_block,
        variable_map=vmap,
        harness=harness,
        definition_lookup=_definition_lookup(bundle),
        given_when_override=given_override or None,
        then_override=then_override or None,
    )
    payload = draft.to_dict()
    if candidate:
        payload["spec_preview"] = {
            "given_when": given_override or materialize_expected_input(candidate, _definition_lookup(bundle)),
            "then": then_override or materialize_expected_output(candidate),
            "use_case": candidate.get("use_case_description") or "",
        }
    elif logic_block:
        payload["spec_preview"] = {
            "logic_expression": logic_block.get("raw_expression") or logic_block.get("expression") or "",
            "control_name": logic_block.get("control_name") or "",
        }
    return payload


def suggest_map_for_request(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str | None = None,
    language: str = "EN",
) -> dict[str, str]:
    harness = GTestHarnessConfig.from_dict(gtest_state.get("harness"))
    candidate = _candidate_by_id(bundle, candidate_id) if candidate_id else None
    wb_row = _workbench_row_for_candidate(bundle, candidate_id, language=language)
    given_when = str(wb_row.get("expected_input") or "").strip() if wb_row else ""
    then_text = str(wb_row.get("expected_output") or "").strip() if wb_row else ""
    if candidate and not given_when:
        given_when = materialize_expected_input(candidate, _definition_lookup(bundle))
    if candidate and not then_text:
        then_text = materialize_expected_output(candidate)
    return suggest_variable_map(
        alias_map=bundle.get("alias_map") or [],
        harness=harness,
        existing=dict(gtest_state.get("code_variable_map") or {}),
        given_when_text=given_when,
        then_text=then_text,
        code_references=bundle.get("code_references") or [],
    )


def save_draft(
    gtest_state: dict[str, Any],
    *,
    draft_key: str,
    draft: dict[str, Any],
    engineer_edited: bool = True,
    wrap_markers: bool = True,
) -> dict[str, Any]:
    payload = dict(draft)
    cid = str(draft_key or "").strip()
    full = str(payload.get("full_snippet") or "").strip()
    if wrap_markers and cid and full and f"// @alex:begin {cid}" not in full:
        payload = wrap_draft_markers(cid, payload, spec_hash=str(payload.get("spec_hash") or ""))
    drafts = dict(gtest_state.get("drafts") or {})
    meta: dict[str, Any] = {}
    for key in (
        "code_status",
        "generation_source",
        "last_saved_at",
        "workflow_error",
        "workflow_message",
        "quality_summary",
        "review_reason",
        "mapping_ready",
    ):
        val = payload.get(key)
        if val is not None and val != "":
            meta[key] = val
    if payload.get("quality_results"):
        meta["quality_results"] = payload.get("quality_results")
    if payload.get("mapping_missing"):
        meta["mapping_missing"] = payload.get("mapping_missing")
    drafts[draft_key] = {
        **payload,
        **meta,
        "updated_at": _now_iso(),
        "engineer_edited": engineer_edited,
    }
    gtest_state["drafts"] = drafts
    gtest_state["updated_at"] = _now_iso()
    return gtest_state


def inject_testcase_id_comment(snippet: str, candidate_id: str) -> str:
    """Ensure testcase id appears in spec comments when missing."""
    cid = str(candidate_id or "").strip()
    text = str(snippet or "")
    if not cid or cid in text:
        return text
    match = re.search(r"\bTEST(?:_F)?\s*\(", text)
    if not match:
        return f"// Testcase: {cid}\n{text}".strip()
    idx = match.start()
    prefix = text[:idx].rstrip()
    inject = f"// Testcase: {cid}"
    if prefix:
        return f"{prefix}\n{inject}\n{text[idx:]}".strip()
    return f"{inject}\n{text[idx:]}".strip()


def _workflow_result(
    code_status: str,
    workflow_message: str,
    prepared_snippet: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code_status": code_status,
        "workflow_status": code_status,
        "workflow_message": workflow_message,
        "prepared_snippet": prepared_snippet,
        "validation": validation,
        "ok": code_status == "SAVED",
    }


def classify_generated_code_workflow(
    code: str,
    *,
    candidate_id: str = "",
    sample_snippet: str = "",
    structured_io: dict[str, Any] | None = None,
    code_rules_md: str = "",
    api_catalog_yaml: str = "",
    expected_input: str = "",
    expected_output: str = "",
) -> dict[str, Any]:
    """Map generated code to SAVED / NEEDS_REVIEW / ERROR using quality gate."""
    from web.code_quality_gate import quality_to_code_status, run_quality_gate

    prepared = inject_testcase_id_comment(str(code or "").strip(), candidate_id)
    qg = run_quality_gate(
        prepared,
        candidate_id=candidate_id,
        structured_io=structured_io,
        code_rules_md=code_rules_md,
        api_catalog_yaml=api_catalog_yaml,
        sample_snippet=sample_snippet,
        expected_input=expected_input,
        expected_output=expected_output,
    )
    if not prepared.strip():
        return _workflow_result("ERROR", "empty result", "", qg)
    status = quality_to_code_status(qg["summary"])
    msg = "generated by API" if status == "SAVED" else "; ".join(
        c["message"] for c in qg.get("checks") or [] if c.get("severity") in ("WARNING", "FAIL")
    )[:400]
    out = _workflow_result(status, msg or status, prepared, qg)
    out["quality_results"] = qg.get("checks") or []
    out["quality_summary"] = qg.get("summary")
    return out


def _split_snippet_for_save(full: str) -> tuple[str, str]:
    body_start = re.search(r"\bTEST(?:_F)?\s*\(", full or "")
    if body_start and body_start.start() > 0:
        return full[: body_start.start()].strip(), full[body_start.start() :].strip()
    if body_start:
        return "", full[body_start.start() :].strip()
    return full.strip(), ""


def persist_generated_draft_workflow(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    draft_payload: dict[str, Any],
    generation_source: str = "API",
    language: str = "EN",
    sample_snippet: str = "",
    code_rules_md: str = "",
    api_catalog_yaml: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    """Validate, classify, and optionally persist a generated draft with workflow metadata."""
    cid = str(candidate_id or "").strip()
    full = str(draft_payload.get("full_snippet") or "").strip()
    if not full:
        body = str(draft_payload.get("code_body") or "").strip()
        spec = str(draft_payload.get("spec_comment_block") or "").strip()
        if spec and body:
            full = f"{spec}\n{body}".strip()
        elif body:
            full = body

    wb = _workbench_row_for_candidate(bundle, cid, language=language) if cid else None
    structured = _structured_io_for_candidate(bundle, cid, language=language) if cid else {}
    cfg_cache = gtest_state.get("project_code_config_cache") or {}
    rules = code_rules_md or str(cfg_cache.get("code_rules.md") or "")
    catalog = api_catalog_yaml or str(cfg_cache.get("api_catalog.yaml") or "")
    wf = classify_generated_code_workflow(
        full,
        candidate_id=cid,
        sample_snippet=sample_snippet,
        structured_io=structured,
        code_rules_md=rules,
        api_catalog_yaml=catalog,
        expected_input=str(wb.get("expected_input") or "") if wb else "",
        expected_output=str(wb.get("expected_output") or "") if wb else "",
    )
    prepared = str(wf.get("prepared_snippet") or "").strip()
    code_status = str(wf.get("code_status") or "ERROR")

    if not prepared and code_status == "ERROR":
        if persist and cid:
            save_draft(
                gtest_state,
                draft_key=cid,
                draft={
                    "full_snippet": "",
                    "code_body": "",
                    "code_status": "ERROR",
                    "workflow_error": wf.get("workflow_message") or "empty result",
                    "generation_source": generation_source,
                    "is_partial_code": False,
                    "is_fallback_scaffold": False,
                    "issue_reason": "parse_error",
                },
                engineer_edited=False,
                wrap_markers=False,
            )
        return {**wf, "candidate_id": cid, "draft": {}}

    spec_block, code_body = _split_snippet_for_save(prepared)
    structured = _structured_io_for_candidate(bundle, cid, language=language) if cid else {}
    spec_hash = compute_spec_hash(structured) if structured else ""
    body_hash = compute_body_hash(structured) if structured else ""

    from web.code_quality_gate import is_partial_generated_code

    _is_partial = is_partial_generated_code(prepared)
    _is_fallback = bool(draft_payload.get("is_fallback_scaffold"))
    _issue_reason = draft_payload.get("issue_reason") or ""
    if not _issue_reason:
        if _is_fallback:
            _issue_reason = "fallback_scaffold_timeout"
        elif _is_partial and code_status == "NEEDS_REVIEW":
            _issue_reason = "partial_code_todo_review"
        elif code_status == "ERROR":
            _issue_reason = "api_error"
        elif code_status == "NEEDS_REVIEW":
            _issue_reason = "needs_review"

    draft_to_save: dict[str, Any] = {
        **draft_payload,
        "full_snippet": prepared,
        "spec_comment_block": spec_block,
        "code_body": code_body,
        "spec_hash": spec_hash,
        "body_hash": body_hash,
        "code_status": code_status,
        "workflow_message": wf.get("workflow_message") or "",
        "generation_source": generation_source,
        "last_saved_at": _now_iso() if code_status == "SAVED" else None,
        "quality_results": wf.get("quality_results") or wf.get("validation", {}).get("checks") or [],
        "quality_summary": wf.get("quality_summary") or draft_payload.get("quality_summary") or "",
        "review_reason": (wf.get("workflow_message") or "") if code_status != "SAVED" else "",
        "is_partial_code": _is_partial,
        "is_fallback_scaffold": _is_fallback,
        "issue_reason": _issue_reason,
    }
    for extra in ("mapping_ready", "mapping_missing"):
        if draft_payload.get(extra) is not None:
            draft_to_save[extra] = draft_payload.get(extra)
    if code_status == "ERROR":
        draft_to_save["workflow_error"] = wf.get("workflow_message") or "save blocked"

    if persist and cid:
        try:
            save_draft(
                gtest_state,
                draft_key=cid,
                draft=draft_to_save,
                engineer_edited=False,
                wrap_markers=bool(prepared),
            )
        except Exception as exc:
            err = f"save failed: {exc}"
            save_draft(
                gtest_state,
                draft_key=cid,
                draft={
                    "full_snippet": prepared,
                    "code_body": code_body,
                    "spec_comment_block": spec_block,
                    "code_status": "ERROR",
                    "workflow_error": err,
                    "generation_source": generation_source,
                },
                engineer_edited=False,
                wrap_markers=bool(prepared),
            )
            return {
                "candidate_id": cid,
                "code_status": "ERROR",
                "workflow_status": "ERROR",
                "workflow_message": err,
                "prepared_snippet": prepared,
                "validation": wf.get("validation") or {},
                "ok": False,
                "draft": (gtest_state.get("drafts") or {}).get(cid) or {},
            }

    saved = (gtest_state.get("drafts") or {}).get(cid) or draft_to_save
    return {**wf, "candidate_id": cid, "draft": saved}


def persist_batch_generation_error(
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    error_message: str,
    generation_source: str = "API",
    persist: bool = True,
) -> None:
    cid = str(candidate_id or "").strip()
    if not cid or not persist:
        return
    save_draft(
        gtest_state,
        draft_key=cid,
        draft={
            "full_snippet": "",
            "code_body": "",
            "code_status": "ERROR",
            "workflow_error": str(error_message or "API failed")[:500],
            "workflow_message": str(error_message or "API failed")[:500],
            "generation_source": generation_source,
        },
        engineer_edited=False,
        wrap_markers=False,
    )


def export_single_snippet(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    candidate_id: str,
) -> str:
    draft_payload = generate_draft_for_request(
        bundle,
        gtest_state,
        candidate_id=candidate_id,
    )
    saved = (gtest_state.get("drafts") or {}).get(candidate_id) or {}
    if saved.get("full_snippet"):
        return str(saved["full_snippet"])
    return str(draft_payload.get("full_snippet") or "")


def export_approved_bundle(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    statuses: set[str] | None = None,
) -> str:
    allowed = statuses or {"approved", "ready"}
    harness = GTestHarnessConfig.from_dict(gtest_state.get("harness"))
    drafts: list[Any] = []
    for cand in bundle.get("test_candidates") or []:
        status = str(cand.get("review_status") or cand.get("status") or "").lower()
        if status not in allowed:
            continue
        cid = str(cand.get("id") or "")
        if not cid:
            continue
        saved = (gtest_state.get("drafts") or {}).get(cid)
        if saved and saved.get("full_snippet"):
            from src.engine.gtest_codegen import GTestDraft

            drafts.append(
                GTestDraft(
                    source_kind=str(saved.get("source_kind") or "candidate"),
                    source_id=cid,
                    test_name=str(saved.get("test_name") or cid),
                    spec_comment_block=str(saved.get("spec_comment_block") or ""),
                    code_body=str(saved.get("code_body") or ""),
                    full_snippet=str(saved.get("full_snippet") or ""),
                )
            )
        else:
            payload = generate_draft_for_request(bundle, gtest_state, candidate_id=cid)
            from src.engine.gtest_codegen import GTestDraft

            drafts.append(
                GTestDraft(
                    source_kind=str(payload.get("source_kind") or "candidate"),
                    source_id=cid,
                    test_name=str(payload.get("test_name") or cid),
                    spec_comment_block=str(payload.get("spec_comment_block") or ""),
                    code_body=str(payload.get("code_body") or ""),
                    full_snippet=str(payload.get("full_snippet") or ""),
                )
            )
    return compose_full_translation_unit(drafts, harness)


def library_preset_path(_library_root: Path | None = None) -> Path:
    """GTest harness preset — always under ALEX/web_data/.alex (not Library root)."""
    del _library_root
    return gtest_preset_path()


def export_library_preset(
    gtest_state: dict[str, Any],
    *,
    project_memory: dict[str, Any] | None = None,
    code_style_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "kind": "alex_gtest_preset",
        "harness": gtest_state.get("harness") or {},
        "code_variable_map": gtest_state.get("code_variable_map") or {},
        "code_style_samples": code_style_samples or [],
        "exported_at": _now_iso(),
    }
    if project_memory:
        payload["project_memory"] = project_memory
    return payload


def import_library_preset(
    gtest_state: dict[str, Any],
    preset: dict[str, Any],
    *,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if preset.get("harness"):
        gtest_state["harness"] = {**(gtest_state.get("harness") or {}), **preset["harness"]}
    if preset.get("code_variable_map"):
        merged = dict(gtest_state.get("code_variable_map") or {})
        merged.update(preset["code_variable_map"])
        gtest_state["code_variable_map"] = merged
    if bundle is not None and preset.get("code_style_samples"):
        from web.code_style_samples import import_library_code_samples

        import_library_code_samples(bundle, {"samples": preset["code_style_samples"]})
    gtest_state["updated_at"] = _now_iso()
    return gtest_state
