"""Orchestrate hybrid GTest generation — Python baseline + M365 Copilot."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any, Callable

from web.copilot_code_context_pack import build_code_context_pack
from web.copilot_code_writer import code_write_batch_size, run_code_refine, run_code_write
from web.gtest_workspace import (
    generate_draft_for_request,
    persist_batch_generation_error,
    persist_generated_draft_workflow,
)

_PACK_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_PACK_CACHE_TTL_S = 300.0


def _cache_key(job_id: str, candidate_id: str, bundle_version: int, language: str) -> str:
    return f"{job_id}:{candidate_id}:{bundle_version}:{language}"


def _cached_context_pack(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    library_root: Path | None,
    language: str,
    include_baseline: bool,
    cfg: dict[str, Any],
    reference_test_name: str,
    library_code_samples: list[dict[str, Any]] | None,
    job_id: str = "",
    bundle_version: int = 0,
) -> dict[str, Any]:
    key = _cache_key(job_id, candidate_id, bundle_version, language) if job_id else ""
    if key:
        hit = _PACK_CACHE.get(key)
        if hit and monotonic() - hit[0] < _PACK_CACHE_TTL_S and not include_baseline:
            pack = dict(hit[1])
            if include_baseline and not pack.get("baseline_skeleton"):
                pass  # fall through to rebuild baseline only
            elif not include_baseline or pack.get("baseline_skeleton"):
                return pack

    pack = build_code_context_pack(
        bundle,
        gtest_state,
        candidate_id=candidate_id,
        library_root=library_root,
        language=language,
        include_baseline=include_baseline,
        cfg=cfg,
        reference_test_name=reference_test_name,
        library_code_samples=library_code_samples,
    )
    if key:
        _PACK_CACHE[key] = (monotonic(), pack)
        if len(_PACK_CACHE) > 64:
            oldest = min(_PACK_CACHE.items(), key=lambda item: item[1][0])[0]
            _PACK_CACHE.pop(oldest, None)
    return pack


def run_copilot_code_generate(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    cfg: dict[str, Any],
    library_root: Path | None = None,
    engineer_note: str = "",
    copilot_prompt_override: str = "",
    use_baseline: bool = True,
    language: str = "EN",
    reference_test_name: str = "",
    library_code_samples: list[dict[str, Any]] | None = None,
    from_testcase_only: bool | None = None,
    reuse_conversation: bool = False,
    slim: bool = True,
    job_id: str = "",
    bundle_version: int = 0,
) -> dict[str, Any]:
    bootstrap = str(bundle.get("bootstrap_source") or "")
    testcase_only = from_testcase_only
    if testcase_only is None:
        testcase_only = bootstrap.startswith("imported")
    try:
        pack = _cached_context_pack(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            library_root=library_root,
            language=language,
            include_baseline=use_baseline,
            cfg=cfg,
            reference_test_name=reference_test_name,
            library_code_samples=library_code_samples,
            job_id=job_id,
            bundle_version=bundle_version,
        )
    except KeyError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "error_category": "no_candidates",
        }
    pack["import_mode"] = bool(testcase_only)
    baseline = pack.get("baseline_skeleton") or {}
    if not baseline and use_baseline:
        baseline = generate_draft_for_request(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            variable_map=pack.get("io_variable_map"),
            language=language,
        )
        pack["baseline_skeleton"] = baseline

    copilot_result = run_code_write(
        pack,
        cfg,
        engineer_note=engineer_note,
        copilot_prompt_override=copilot_prompt_override,
        reuse_conversation=reuse_conversation,
        slim=slim,
    )
    copilot_draft = copilot_result.get("draft") or {}

    if not copilot_result.get("ok"):
        baseline_snippet = baseline.get("full_snippet") or baseline.get("code_body") or ""
        if baseline_snippet:
            fallback_draft = dict(baseline)
            if not fallback_draft.get("full_snippet"):
                fallback_draft["full_snippet"] = baseline_snippet
            return {
                "ok": True,
                "copilot_fallback": True,
                "copilot_unavailable": copilot_result.get("error"),
                "error_category": copilot_result.get("error_category"),
                "context_pack": pack,
                "baseline": baseline,
                "copilot_draft": fallback_draft,
                "validation": {"ok": True, "quality": "baseline", "flags": ["copilot_fallback"]},
                "provider": "offline_baseline",
                "raw_preview": copilot_result.get("raw_preview"),
            }
        return {
            "ok": False,
            "context_pack": pack,
            "baseline": baseline,
            "copilot_draft": copilot_draft,
            "validation": copilot_result.get("validation") or {},
            "provider": copilot_result.get("provider"),
            "error": copilot_result.get("error") or "Copilot did not return valid GTest JSON",
            "error_category": copilot_result.get("error_category") or "m365_copilot_api",
            "raw_preview": copilot_result.get("raw_preview"),
            "user_action": copilot_result.get("user_action"),
        }

    return {
        "ok": copilot_result.get("ok"),
        "context_pack": pack,
        "baseline": baseline,
        "copilot_draft": copilot_draft,
        "validation": copilot_result.get("validation") or {},
        "provider": copilot_result.get("provider"),
        "error": None if copilot_result.get("ok") else "Copilot did not return valid GTest JSON",
        "raw_preview": copilot_result.get("raw_preview"),
    }


def run_copilot_code_refine(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    existing_code: str,
    instruction: str,
    cfg: dict[str, Any],
    library_root: Path | None = None,
    language: str = "EN",
    reference_test_name: str = "",
    library_code_samples: list[dict[str, Any]] | None = None,
    reuse_conversation: bool = False,
    job_id: str = "",
    bundle_version: int = 0,
) -> dict[str, Any]:
    try:
        pack = _cached_context_pack(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            library_root=library_root,
            language=language,
            include_baseline=False,
            cfg=cfg,
            reference_test_name=reference_test_name,
            library_code_samples=library_code_samples,
            job_id=job_id,
            bundle_version=bundle_version,
        )
    except KeyError as exc:
        return {"ok": False, "error": str(exc), "error_category": "no_candidates"}
    pack["existing_draft"] = str(existing_code or "").strip()
    result = run_code_refine(
        existing_code,
        instruction,
        cfg,
        test_name=candidate_id,
        context_pack=pack,
        reuse_conversation=reuse_conversation,
    )
    return {"ok": bool(result.get("ok")), "context_pack": pack, **result}


def run_copilot_code_generate_batch(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str],
    cfg: dict[str, Any],
    library_root: Path | None = None,
    engineer_note: str = "",
    copilot_prompt_override: str = "",
    language: str = "EN",
    reference_test_name: str = "",
    library_code_samples: list[dict[str, Any]] | None = None,
    persist_drafts: bool = False,
    slim: bool = True,
    job_id: str = "",
    bundle_version: int = 0,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    batch_size = code_write_batch_size(cfg)
    sample_snippet = ""
    if library_code_samples:
        sample_snippet = str((library_code_samples[0] or {}).get("snippet") or "")
    cfg_cache = gtest_state.get("project_code_config_cache") or {}
    code_rules_md = str(cfg_cache.get("code_rules.md") or "")
    api_catalog_yaml = str(cfg_cache.get("api_catalog.yaml") or "")
    results: list[dict[str, Any]] = []
    saved_count = 0
    needs_review_count = 0
    error_count = 0
    skip_count = 0

    for idx, cid in enumerate(candidate_ids):
        if cancel_check and cancel_check():
            break
        if progress_callback:
            progress_callback(idx, len(candidate_ids), f"Copilot batch {idx + 1}/{len(candidate_ids)}…")
        try:
            one = run_copilot_code_generate(
                bundle,
                gtest_state,
                candidate_id=cid,
                cfg=cfg,
                library_root=library_root,
                engineer_note=engineer_note,
                copilot_prompt_override=copilot_prompt_override,
                language=language,
                reference_test_name=reference_test_name,
                library_code_samples=library_code_samples,
                slim=slim,
                job_id=job_id,
                bundle_version=bundle_version,
            )
        except KeyError as exc:
            msg = str(exc)
            if persist_drafts:
                persist_batch_generation_error(gtest_state, candidate_id=cid, error_message=msg)
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "error": msg,
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                }
            )
            error_count += 1
            continue

        copilot_draft = one.get("copilot_draft") or one.get("draft") or {}
        if not one.get("ok") or not (
            copilot_draft.get("full_snippet") or copilot_draft.get("code_body")
        ):
            msg = str(one.get("error") or "API failed")
            if persist_drafts:
                persist_batch_generation_error(gtest_state, candidate_id=cid, error_message=msg)
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "error": msg,
                    "copilot_draft": copilot_draft,
                    "validation": one.get("validation") or {},
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                }
            )
            error_count += 1
            continue

        wf: dict[str, Any]
        if persist_drafts:
            wf = persist_generated_draft_workflow(
                bundle,
                gtest_state,
                candidate_id=cid,
                draft_payload={**copilot_draft, "source_kind": "copilot"},
                generation_source="API",
                language=language,
                sample_snippet=sample_snippet,
                code_rules_md=code_rules_md,
                api_catalog_yaml=api_catalog_yaml,
                persist=True,
            )
        else:
            from web.gtest_workspace import classify_generated_code_workflow

            full = str(copilot_draft.get("full_snippet") or copilot_draft.get("code_body") or "")
            wf = classify_generated_code_workflow(
                full,
                candidate_id=cid,
                sample_snippet=sample_snippet,
                code_rules_md=code_rules_md,
                api_catalog_yaml=api_catalog_yaml,
            )
            wf = {**wf, "candidate_id": cid, "draft": copilot_draft}

        wf_status = str(wf.get("workflow_status") or wf.get("code_status") or "ERROR")
        if wf_status == "SAVED":
            saved_count += 1
        elif wf_status == "NEEDS_REVIEW":
            needs_review_count += 1
        elif wf_status == "ERROR":
            error_count += 1

        entry = {
            "candidate_id": cid,
            "ok": wf_status == "SAVED",
            "copilot_draft": wf.get("draft") or copilot_draft,
            "validation": wf.get("validation") or one.get("validation") or {},
            "error": one.get("error"),
            "workflow_status": wf_status,
            "workflow_message": wf.get("workflow_message") or "",
            "code_status": wf.get("code_status") or wf_status,
            "generation_source": "API" if wf_status == "SAVED" else "",
        }
        results.append(entry)

        if len([r for r in results if not r.get("skipped")]) % batch_size == 0:
            pass  # pacing hook for future rate-limit sleep

    gtest_state.setdefault("copilot_batch", {})["last_results"] = results
    gtest_state["updated_at"] = gtest_state.get("updated_at") or ""

    return {
        "ok": saved_count > 0,
        "total": len(candidate_ids),
        "generated": saved_count,
        "saved": saved_count,
        "needs_review": needs_review_count,
        "skipped": skip_count,
        "failed": error_count,
        "error": error_count,
        "results": results,
        "batch_size": batch_size,
        "summary": {
            "saved": saved_count,
            "needs_review": needs_review_count,
            "error": error_count,
            "skipped": skip_count,
            "total": len(candidate_ids),
        },
    }
