"""Mapping coverage and local template-based GTest generation."""

from __future__ import annotations

import re
from typing import Any

from web.ai_providers import LOCAL_TEMPLATE
from web.code_quality_gate import quality_to_code_status, run_quality_gate
from web.config_yaml_parsers import (
    build_mapping_match_index,
    flatten_signal_mapping,
    parse_signal_mapping_yaml,
    resolve_signal_mapping_match,
)
from web.gtest_workspace import (
    _structured_io_for_candidate,
    _workbench_row_for_candidate,
    generate_draft_for_request,
    persist_generated_draft_workflow,
    persist_batch_generation_error,
)
from web.project_code_config import load_project_code_config

_TERM_RE = re.compile(r"^Given:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=", re.I | re.M)
_THEN_RE = re.compile(r"^Then:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=", re.I | re.M)


def _extract_io_signals(expected_input: str, expected_output: str) -> tuple[set[str], set[str]]:
    given: set[str] = set()
    then: set[str] = set()
    for line in f"{expected_input}\n{expected_output}".splitlines():
        s = line.strip()
        gm = _TERM_RE.match(s)
        if gm:
            given.add(gm.group("sig"))
        tm = _THEN_RE.match(s)
        if tm:
            then.add(tm.group("sig"))
    return given, then


def _merged_mapping(gtest_state: dict[str, Any], config_files: dict[str, Any]) -> dict[str, str]:
    out = dict(gtest_state.get("code_variable_map") or {})
    sm = config_files.get("signal_mapping.yaml") or {}
    parsed = parse_signal_mapping_yaml(str(sm.get("content") or ""))
    out.update(flatten_signal_mapping(parsed))
    return out


def check_candidate_mapping(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    candidate_id: str,
    *,
    config: dict[str, Any] | None = None,
    language: str = "EN",
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    files = config.get("files") or {}
    if index is None:
        index = build_mapping_match_index(gtest_state, files)
    wb = _workbench_row_for_candidate(bundle, candidate_id, language=language) or {}
    inp = str(wb.get("expected_input") or "").strip()
    out = str(wb.get("expected_output") or "").strip()
    if not inp or not out:
        return {
            "candidate_id": candidate_id,
            "ready": False,
            "missing_terms": ["expected_input", "expected_output"],
            "reason": "missing I/O",
            "matched": [],
        }
    given, then = _extract_io_signals(inp, out)
    missing: list[str] = []
    matched: list[dict[str, Any]] = []
    for sig in sorted(given | then):
        hit = resolve_signal_mapping_match(sig, index)
        if hit:
            matched.append(hit)
        else:
            missing.append(sig)
    return {
        "candidate_id": candidate_id,
        "ready": len(missing) == 0,
        "missing_terms": missing,
        "matched": matched,
        "reason": "ok" if not missing else "missing mapping",
    }


def check_mapping_coverage(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    *,
    language: str = "EN",
) -> dict[str, Any]:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    config = load_project_code_config(job_output)
    files = config.get("files") or {}
    index = build_mapping_match_index(gtest_state, files)
    detected_mapping_count = int(index.get("detected_mapping_count") or 0)

    preview = build_customer_testspec_preview(bundle, language=language)
    rows = preview.get("rows") or []
    per_case: list[dict[str, Any]] = []
    ready = 0
    missing_count = 0
    all_missing_terms: set[str] = set()
    affected: list[str] = []
    sample_matched: list[dict[str, Any]] = []

    for row in rows:
        cid = str(row.get("candidate_id") or "").strip()
        if not cid:
            continue
        one = check_candidate_mapping(
            bundle, gtest_state, cid, config=config, language=language, index=index
        )
        per_case.append(one)
        if one["ready"]:
            ready += 1
            for m in one.get("matched") or []:
                if len(sample_matched) < 12:
                    sample_matched.append({"testcase_id": cid, **m})
        else:
            missing_count += 1
            affected.append(cid)
            all_missing_terms.update(one.get("missing_terms") or [])

    warnings: list[str] = []
    if ready == 0 and detected_mapping_count > 0:
        warnings.append(
            "Mappings were detected, but testcase terms did not match. Check naming/aliases."
        )

    top_missing = sorted(all_missing_terms)[:15]
    coverage_payload = {
        "total": len(per_case),
        "ready_for_local_generation": ready,
        "missing_mapping_count": missing_count,
        "needs_review_count": 0,
        "missing_terms": sorted(all_missing_terms),
        "top_missing_terms": top_missing,
        "affected_testcase_ids": affected,
        "detected_mapping_count": detected_mapping_count,
        "sample_matched_mappings": sample_matched,
        "warnings": warnings,
        "cases": per_case,
    }
    gtest_state["mapping_coverage"] = coverage_payload

    return {
        "ok": True,
        "total_testcase_count": len(per_case),
        "ready_for_local_generation": ready,
        "missing_mapping_count": missing_count,
        "needs_review_count": 0,
        "missing_terms": sorted(all_missing_terms),
        "top_missing_terms": top_missing,
        "affected_testcase_ids": affected,
        "detected_mapping_count": detected_mapping_count,
        "sample_matched_mappings": sample_matched,
        "warnings": warnings,
        "cases": per_case,
    }


def generate_local_template_for_candidate(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    candidate_id: str,
    *,
    language: str = "EN",
    sample_snippet: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    config = load_project_code_config(job_output)
    files = config.get("files") or {}
    cov = check_candidate_mapping(bundle, gtest_state, candidate_id, config=config, language=language)
    if not cov["ready"]:
        msg = f"missing mapping: {', '.join(cov.get('missing_terms') or [])}"
        if persist:
            persist_batch_generation_error(
                gtest_state, candidate_id=candidate_id, error_message=msg, generation_source=LOCAL_TEMPLATE
            )
        return {
            "candidate_id": candidate_id,
            "ok": False,
            "workflow_status": "ERROR",
            "code_status": "ERROR",
            "workflow_message": msg,
            "mapping_missing": cov.get("missing_terms") or [],
        }

    vmap = _merged_mapping(gtest_state, files)
    draft_payload = generate_draft_for_request(
        bundle,
        gtest_state,
        candidate_id=candidate_id,
        variable_map=vmap,
        language=language,
    )
    full = str(draft_payload.get("full_snippet") or draft_payload.get("code_body") or "").strip()
    wb = _workbench_row_for_candidate(bundle, candidate_id, language=language) or {}
    structured = _structured_io_for_candidate(bundle, candidate_id, language=language)
    qg = run_quality_gate(
        full,
        candidate_id=candidate_id,
        structured_io=structured,
        code_rules_md=str((files.get("code_rules.md") or {}).get("content") or ""),
        api_catalog_yaml=str((files.get("api_catalog.yaml") or {}).get("content") or ""),
        sample_snippet=sample_snippet,
        expected_input=str(wb.get("expected_input") or ""),
        expected_output=str(wb.get("expected_output") or ""),
    )
    code_status = quality_to_code_status(qg["summary"])
    review_reason = ""
    if code_status != "SAVED":
        review_reason = "; ".join(
            c["message"] for c in qg.get("checks") or [] if c.get("severity") in ("WARNING", "FAIL")
        )[:500]

    draft_payload["quality_results"] = qg.get("checks") or []
    draft_payload["quality_summary"] = qg.get("summary") or "FAIL"
    draft_payload["mapping_ready"] = True
    draft_payload["mapping_missing"] = []
    draft_payload["review_reason"] = review_reason

    if persist:
        wf = persist_generated_draft_workflow(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            draft_payload={**draft_payload, "source_kind": "local_template"},
            generation_source=LOCAL_TEMPLATE,
            language=language,
            sample_snippet=sample_snippet,
            persist=True,
        )
        saved = wf.get("draft") or {}
        saved["quality_results"] = qg.get("checks") or []
        saved["quality_summary"] = qg.get("summary")
        return {
            **wf,
            "quality": qg,
            "mapping": cov,
        }

    return {
        "candidate_id": candidate_id,
        "ok": code_status == "SAVED",
        "workflow_status": code_status if code_status != "SAVED" else "SAVED",
        "code_status": code_status,
        "workflow_message": review_reason or "generated by local template",
        "quality": qg,
        "draft": draft_payload,
    }


def batch_generate_local_template(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    sample_snippet: str = "",
) -> dict[str, Any]:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    coverage = check_mapping_coverage(bundle, gtest_state, job_output, language=language)
    ready_set = {
        c["candidate_id"]
        for c in coverage.get("cases") or []
        if c.get("ready") and c.get("candidate_id")
    }
    preview = build_customer_testspec_preview(bundle, language=language)
    all_ids = [str(r.get("candidate_id") or "") for r in preview.get("rows") or [] if r.get("candidate_id")]
    targets = [c for c in (candidate_ids or all_ids) if c in ready_set]
    results: list[dict[str, Any]] = []
    saved = 0
    review = 0
    err = 0
    skipped = 0

    for cid in all_ids:
        if candidate_ids is not None and cid not in candidate_ids:
            continue
        if cid not in ready_set:
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "skipped": True,
                    "workflow_status": "skipped",
                    "workflow_message": "missing mapping — not generated",
                }
            )
            skipped += 1
            continue
        if cid not in targets:
            continue
        one = generate_local_template_for_candidate(
            bundle,
            gtest_state,
            job_output,
            cid,
            language=language,
            sample_snippet=sample_snippet,
            persist=True,
        )
        results.append(one)
        st = str(one.get("workflow_status") or one.get("code_status") or "ERROR")
        if st == "SAVED":
            saved += 1
        elif st == "NEEDS_REVIEW":
            review += 1
        else:
            err += 1

    return {
        "ok": saved > 0,
        "results": results,
        "summary": {
            "saved": saved,
            "needs_review": review,
            "error": err,
            "skipped": skipped,
            "total": len(results),
        },
        "mapping_coverage": coverage,
    }
