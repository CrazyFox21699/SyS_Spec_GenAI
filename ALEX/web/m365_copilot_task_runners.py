"""Execute M365 Copilot background tasks by kind."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from web.copilot_code_orchestrator import run_copilot_code_generate, run_copilot_code_generate_batch, run_copilot_code_refine
from web.copilot_orchestrator import build_context, run_plan, run_write
from web.copilot_row_assist import preview_row_draft, write_from_row_via_copilot
from web.gtest_workspace import save_draft
from web.m365_copilot_tasks import is_cancelled
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview


ProgressFn = Callable[[str], None]


def _check_cancelled(job_id: str, task: dict[str, Any]) -> None:
    if is_cancelled(job_id, str(task.get("task_id") or "")):
        raise RuntimeError("Task cancelled")


def run_task_kind(
    kind: str,
    *,
    job_id: str,
    payload: dict[str, Any],
    task: dict[str, Any],
    progress: ProgressFn,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    cfg: dict[str, Any],
    library_root: Path | None,
    library_code_samples: list[dict[str, Any]] | None,
    save_bundle: Callable[[dict[str, Any]], None],
    persist_gtest: Callable[[dict[str, Any]], None],
    job_output: Path | None = None,
) -> dict[str, Any]:
    if kind == "code_generate":
        return _run_code_generate(
            payload, task, progress, job_id, bundle, gtest_state, cfg, library_root, library_code_samples
        )
    if kind == "code_refine":
        return _run_code_refine(
            payload,
            progress,
            job_id,
            bundle,
            gtest_state,
            cfg,
            library_root,
            library_code_samples,
        )
    if kind == "code_copilot_batch":
        return _run_code_copilot_batch(
            payload,
            task,
            progress,
            job_id,
            bundle,
            gtest_state,
            cfg,
            persist_gtest,
            job_output=job_output,
        )
    if kind == "code_exemplar_batch":
        return _run_code_exemplar_batch(
            payload,
            task,
            progress,
            job_id,
            bundle,
            gtest_state,
            cfg,
            persist_gtest,
        )
    if kind == "code_batch":
        return _run_code_batch(
            payload,
            task,
            progress,
            job_id,
            bundle,
            gtest_state,
            cfg,
            library_root,
            library_code_samples,
            persist_gtest,
        )
    if kind == "copilot_plan":
        return _run_copilot_plan(payload, progress, bundle, cfg, save_bundle)
    if kind == "copilot_write":
        return _run_copilot_write(payload, progress, bundle, cfg, save_bundle)
    if kind == "copilot_context_plan":
        return _run_copilot_context_plan(payload, progress, bundle, cfg, save_bundle)
    if kind == "write_from_row":
        return _run_write_from_row(payload, progress, bundle, cfg)
    return {"ok": False, "error": f"Unknown kind: {kind}", "error_category": "validation"}


def _run_code_generate(
    payload: dict[str, Any],
    task: dict[str, Any],
    progress: ProgressFn,
    job_id: str,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    cfg: dict[str, Any],
    library_root: Path | None,
    library_code_samples: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    progress("Building context…")
    _check_cancelled(job_id, task)
    result = run_copilot_code_generate(
        bundle,
        gtest_state,
        candidate_id=str(payload.get("candidate_id") or ""),
        cfg=cfg,
        library_root=library_root,
        engineer_note=str(payload.get("engineer_note") or ""),
        copilot_prompt_override=str(payload.get("copilot_prompt_override") or ""),
        use_baseline=bool(payload.get("use_baseline", True)),
        language=str(payload.get("language") or "EN"),
        reference_test_name=str(payload.get("reference_test_name") or ""),
        library_code_samples=library_code_samples,
        from_testcase_only=payload.get("from_testcase_only"),
        reuse_conversation=bool(payload.get("reuse_conversation", True)),
        slim=bool(payload.get("slim", True)),
        bundle_version=int(payload.get("bundle_version") or 0),
        job_id=job_id,
    )
    return {"ok": bool(result.get("ok")), **result}


def _run_code_refine(
    payload: dict[str, Any],
    progress: ProgressFn,
    job_id: str,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    cfg: dict[str, Any],
    library_root: Path | None,
    library_code_samples: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    progress("Copilot refine…")
    result = run_copilot_code_refine(
        bundle,
        gtest_state,
        candidate_id=str(payload.get("candidate_id") or ""),
        existing_code=str(payload.get("existing_code") or ""),
        instruction=str(payload.get("instruction") or ""),
        cfg=cfg,
        library_root=library_root,
        language=str(payload.get("language") or "EN"),
        reference_test_name=str(payload.get("reference_test_name") or ""),
        library_code_samples=library_code_samples,
        reuse_conversation=bool(payload.get("reuse_conversation", True)),
        job_id=job_id,
        bundle_version=int(payload.get("bundle_version") or 0),
    )
    if result.get("ok"):
        return {
            "ok": True,
            "copilot_draft": result.get("draft") or {},
            "validation": result.get("validation") or {},
            "provider": result.get("provider"),
            "review_note": result.get("error"),
        }
    return result


def _run_code_copilot_batch(
    payload: dict[str, Any],
    task: dict[str, Any],
    progress: ProgressFn,
    job_id: str,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    cfg: dict[str, Any],
    persist_gtest: Callable[[dict[str, Any]], None],
    job_output: Path | None = None,
) -> dict[str, Any]:
    from web.copilot_batch_codegen import run_copilot_batch_api

    progress("Copilot API chunks…", current=0, total=1)
    result = run_copilot_batch_api(
        bundle,
        gtest_state,
        job_output,
        cfg=cfg,
        candidate_ids=[c for c in (payload.get("candidate_ids") or []) if c],
        language=str(payload.get("language") or "EN"),
        engineer_note=str(payload.get("engineer_note") or ""),
        clarification_note=str(payload.get("clarification_note") or ""),
        batch_size=int(payload.get("batch_size") or 10),
        skip_saved=bool(payload.get("skip_saved")),
        scope=str(payload.get("scope") or "filter"),
        group_key=str(payload.get("group_key") or ""),
        group_field=str(payload.get("group_field") or "test_group"),
        retry_count=int(payload.get("retry_count") or 0),
        user_id=str(payload.get("m365_user_id") or "") or None,
        allow_missing_sample=bool(payload.get("allow_missing_sample", True)),
        slim_prompt=bool(payload.get("slim_prompt", True)),
        prompt_budget=int(payload.get("prompt_budget") or 5000),
        progress_callback=lambda cur, tot, msg, **extra: progress(
            msg, current=cur + 1, total=tot, **extra
        ),
        cancel_check=lambda: is_cancelled(job_id, str(task.get("task_id") or "")),
    )
    persist_gtest(gtest_state)
    return {"ok": bool(result.get("ok")), **result}


def _run_code_exemplar_batch(
    payload: dict[str, Any],
    task: dict[str, Any],
    progress: ProgressFn,
    job_id: str,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    cfg: dict[str, Any],
    persist_gtest: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    from web.exemplar_batch_codegen import run_exemplar_batch_api

    progress("Exemplar batch API…", current=0, total=1)
    result = run_exemplar_batch_api(
        bundle,
        gtest_state,
        None,
        cfg=cfg,
        candidate_ids=[c for c in (payload.get("candidate_ids") or []) if c],
        language=str(payload.get("language") or "EN"),
        engineer_note=str(payload.get("engineer_note") or ""),
        scope=str(payload.get("scope") or "filter"),
        group_key=str(payload.get("group_key") or ""),
        group_field=str(payload.get("group_field") or "test_group"),
        progress_callback=lambda cur, tot, msg: progress(msg, current=cur, total=tot),
        cancel_check=lambda: is_cancelled(job_id, str(task.get("task_id") or "")),
    )
    persist_gtest(gtest_state)
    return {"ok": bool(result.get("ok")), **result}


def _run_code_batch(
    payload: dict[str, Any],
    task: dict[str, Any],
    progress: ProgressFn,
    job_id: str,
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    cfg: dict[str, Any],
    library_root: Path | None,
    library_code_samples: list[dict[str, Any]] | None,
    persist_gtest: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    candidate_ids = [c for c in (payload.get("candidate_ids") or []) if c]

    total = len(candidate_ids)
    progress(f"Copilot batch 0/{total}…", current=0, total=total)
    result = run_copilot_code_generate_batch(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        cfg=cfg,
        library_root=library_root,
        engineer_note=str(payload.get("engineer_note") or ""),
        copilot_prompt_override=str(payload.get("copilot_prompt_override") or ""),
        language=str(payload.get("language") or "EN"),
        reference_test_name=str(payload.get("reference_test_name") or ""),
        library_code_samples=library_code_samples,
        persist_drafts=bool(payload.get("persist_drafts", True)),
        slim=bool(payload.get("slim", True)),
        job_id=job_id,
        bundle_version=int(payload.get("bundle_version") or 0),
        progress_callback=lambda cur, tot, msg: progress(msg, current=cur, total=tot),
        cancel_check=lambda: is_cancelled(job_id, str(task.get("task_id") or "")),
    )
    persist_gtest(gtest_state)
    return {"ok": bool(result.get("ok")), **result}


def _run_copilot_plan(
    payload: dict[str, Any],
    progress: ProgressFn,
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    save_bundle: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    logic_id = str(payload.get("logic_id") or "")
    progress("Generating plan…")
    result = run_plan(
        bundle,
        logic_id,
        cfg,
        engineer_note=str(payload.get("note") or payload.get("engineer_note") or ""),
        focus_term=str(payload.get("term") or payload.get("focus_term") or ""),
    )
    if result.get("ok"):
        save_bundle(bundle)
    return result


def _run_copilot_write(
    payload: dict[str, Any],
    progress: ProgressFn,
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    save_bundle: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    logic_id = str(payload.get("logic_id") or "")
    progress("Writing testcases via Copilot…")
    result = run_write(bundle, logic_id, cfg)
    if result.get("ok"):
        save_bundle(bundle)
    return result


def _run_copilot_context_plan(
    payload: dict[str, Any],
    progress: ProgressFn,
    bundle: dict[str, Any],
    cfg: dict[str, Any],
    save_bundle: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    logic_id = str(payload.get("logic_id") or "")
    note = str(payload.get("note") or payload.get("engineer_note") or "")
    term = str(payload.get("term") or payload.get("focus_term") or "")
    progress("Building context…")
    ctx = build_context(bundle, logic_id, engineer_note=note, focus_term=term, cfg=cfg)
    if not ctx.get("ok"):
        return ctx
    progress("Generating plan…")
    result = run_plan(bundle, logic_id, cfg, engineer_note=note, focus_term=term)
    if result.get("ok"):
        save_bundle(bundle)
    return {"ok": bool(result.get("ok")), "context": True, **result}


def _run_write_from_row(
    payload: dict[str, Any],
    progress: ProgressFn,
    bundle: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    progress("Copilot row assist…")
    language = str(payload.get("language") or "EN")
    preview = build_customer_testspec_preview(bundle, language=language)
    row = next(
        (r for r in preview.get("rows") or [] if str(r.get("candidate_id") or "") == str(payload.get("candidate_id") or "")),
        None,
    )
    if not row:
        return {"ok": False, "error": f"Test case not found: {payload.get('candidate_id')}"}
    result = write_from_row_via_copilot(cfg, row, engineer_note=str(payload.get("engineer_note") or ""))
    if not result.get("ok"):
        return result
    draft = result.get("draft") or {}
    preview_result = preview_row_draft(bundle, row, draft)
    return {"ok": True, **result, **preview_result}
