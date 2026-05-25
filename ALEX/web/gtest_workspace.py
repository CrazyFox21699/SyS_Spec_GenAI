"""GTest workspace helpers — load/save drafts, generate snippets, library presets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
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

GTEST_ARTIFACT = "gtest.json"
LIBRARY_PRESET_NAME = "gtest_harness_preset.yaml"


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
    base["updated_at"] = data.get("updated_at") or base["updated_at"]
    return base


def save_gtest_state(job_output: Path, state: dict[str, Any]) -> None:
    path = gtest_store_path(job_output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "harness": state.get("harness") or {},
        "code_variable_map": state.get("code_variable_map") or {},
        "drafts": state.get("drafts") or {},
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
) -> dict[str, Any]:
    harness = GTestHarnessConfig.from_dict(gtest_state.get("harness"))
    variable_map = dict(gtest_state.get("code_variable_map") or {})
    preview = build_customer_testspec_preview(bundle, language=language)
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
    return {
        "harness": harness.to_dict(),
        "code_variable_map": variable_map,
        "drafts": gtest_state.get("drafts") or {},
        "signals": collect_signal_names(bundle),
        "logic_items": logic_items,
        "workbench_rows": preview.get("rows") or [],
        "code_references": bundle.get("code_references") or [],
    }


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
) -> dict[str, Any]:
    drafts = dict(gtest_state.get("drafts") or {})
    drafts[draft_key] = {
        **draft,
        "updated_at": _now_iso(),
        "engineer_edited": engineer_edited,
    }
    gtest_state["drafts"] = drafts
    gtest_state["updated_at"] = _now_iso()
    return gtest_state


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


def library_preset_path(library_root: Path) -> Path:
    return library_root / ".alex" / LIBRARY_PRESET_NAME


def export_library_preset(gtest_state: dict[str, Any], *, project_memory: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "kind": "alex_gtest_preset",
        "harness": gtest_state.get("harness") or {},
        "code_variable_map": gtest_state.get("code_variable_map") or {},
        "exported_at": _now_iso(),
    }
    if project_memory:
        payload["project_memory"] = project_memory
    return payload


def import_library_preset(gtest_state: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    if preset.get("harness"):
        gtest_state["harness"] = {**(gtest_state.get("harness") or {}), **preset["harness"]}
    if preset.get("code_variable_map"):
        merged = dict(gtest_state.get("code_variable_map") or {})
        merged.update(preset["code_variable_map"])
        gtest_state["code_variable_map"] = merged
    gtest_state["updated_at"] = _now_iso()
    return gtest_state
