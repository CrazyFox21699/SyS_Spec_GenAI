"""Exemplar-based batch GTest generation — style reference for existing import groups only."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from web.code_style_samples import load_code_style_samples
from web.copilot_code_writer import parse_copilot_cpp_response
from web.gtest_workspace import (
    _workbench_row_for_candidate,
    persist_batch_generation_error,
    persist_generated_draft_workflow,
)
from web.copilot_batch_codegen import (
    apply_copilot_batch_import,
    get_code_exemplar,
    parse_copilot_batch_response,
)
from web.batch_target_resolution import import_group_key
from web.m365_copilot import run_copilot_chat_result

_EXEMPLAR_BATCH_MAX_PROMPT_CHARS = 28_000
_EXEMPLAR_BATCH_MIN_CHUNK = 5
_EXEMPLAR_BATCH_MAX_CHUNK = 18
_EXEMPLAR_BATCH_TARGET_CHARS = 1_400

_TESTCASE_CODE_SECTION_RE = re.compile(
    r"\[TESTCASE_CODE\](.*?)(?=\[ASSUMPTIONS\]|\[UNRESOLVED\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_ASSUMPTIONS_SECTION_RE = re.compile(
    r"\[ASSUMPTIONS\](.*?)(?=\[UNRESOLVED\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_UNRESOLVED_SECTION_RE = re.compile(r"\[UNRESOLVED\](.*)$", re.IGNORECASE | re.DOTALL)
_TEST_F_FIXTURE_RE = re.compile(r"TEST_F\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,", re.I)
_BLOCK_RE = re.compile(
    r"testcase_id\s*:\s*([A-Za-z0-9_]+)\s*(?:\n\s*)?```(?:cpp|c\+\+)?\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _draft_full_snippet(draft: dict[str, Any]) -> str:
    full = str(draft.get("full_snippet") or "").strip()
    if full:
        return full
    spec = str(draft.get("spec_comment_block") or "").strip()
    body = str(draft.get("code_body") or "").strip()
    if spec and body:
        return f"{spec}\n{body}".strip()
    return body


def _infer_style_notes(code: str, draft: dict[str, Any]) -> str:
    notes: list[str] = []
    fm = _TEST_F_FIXTURE_RE.search(code)
    if fm:
        notes.append(f"fixture={fm.group(1)}")
    if "EXPECT_CALL" in code:
        notes.append("uses EXPECT_CALL")
    if "EXPECT_THAT" in code:
        notes.append("uses EXPECT_THAT")
    if "igsw_Main_Run" in code:
        notes.append("calls igsw_Main_Run()")
    qs = str(draft.get("quality_summary") or "").upper()
    if qs:
        notes.append(f"quality={qs}")
    return "; ".join(notes)


def mark_code_exemplar(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    candidate_id: str,
    *,
    language: str = "EN",
) -> dict[str, Any]:
    cid = str(candidate_id or "").strip()
    if not cid:
        return {"ok": False, "error": "candidate_id required"}
    draft = (gtest_state.get("drafts") or {}).get(cid) or {}
    code = _draft_full_snippet(draft)
    if not code or not re.search(r"\bTEST(?:_F)?\s*\(", code):
        return {"ok": False, "error": "Save exemplar GTest code (TEST/TEST_F) for this testcase first."}

    wb = _workbench_row_for_candidate(bundle, cid, language=language) or {}
    samples = load_code_style_samples(bundle)
    sample_snippet = ""
    sample_label = ""
    if samples:
        sample_snippet = str((samples[0] or {}).get("snippet") or "")[:12_000]
        sample_label = str((samples[0] or {}).get("label") or (samples[0] or {}).get("source_file") or "")

    exemplar = {
        "candidate_id": cid,
        "marked_at": _now_iso(),
        "test_name": str(draft.get("test_name") or cid),
        "expected_input": str(wb.get("expected_input") or "").strip(),
        "expected_output": str(wb.get("expected_output") or "").strip(),
        "generated_code": code[:24_000],
        "sample_snippet": sample_snippet,
        "sample_label": sample_label,
        "style_notes": _infer_style_notes(code, draft),
        "code_status": str(draft.get("code_status") or ""),
        "test_group": import_group_key(wb),
        "import_group": import_group_key(wb),
        "event": str(wb.get("event") or wb.get("test_function") or "").strip(),
    }
    gtest_state["code_exemplar"] = exemplar
    return {"ok": True, "exemplar": exemplar}


def clear_code_exemplar(gtest_state: dict[str, Any]) -> dict[str, Any]:
    gtest_state.pop("code_exemplar", None)
    return {"ok": True}


def resolve_exemplar_target_ids(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    exclude_exemplar: bool = True,
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
) -> list[str]:
    """Resolve batch targets from import grouping only (no similarity inference)."""
    from web.batch_target_resolution import resolve_batch_targets

    exemplar = get_code_exemplar(gtest_state)
    ex_id = str(exemplar.get("candidate_id") or "") if exemplar else ""
    exclude = [ex_id] if exclude_exemplar and ex_id else None
    resolved = resolve_batch_targets(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        language=language,
        scope=scope,
        group_key=group_key,
        group_field=group_field,
        exclude_candidate_ids=exclude,
    )
    return list(resolved.get("candidate_ids") or [])


def _chunk_targets(target_ids: list[str], row_by_id: dict[str, dict[str, Any]]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for cid in target_ids:
        row = row_by_id.get(cid) or {}
        est = _EXEMPLAR_BATCH_TARGET_CHARS + len(str(row.get("expected_input") or "")) + len(
            str(row.get("expected_output") or "")
        )
        would_exceed = current and (
            len(current) >= _EXEMPLAR_BATCH_MAX_CHUNK
            or current_chars + est > _EXEMPLAR_BATCH_MAX_PROMPT_CHARS
        )
        if would_exceed and len(current) >= _EXEMPLAR_BATCH_MIN_CHUNK:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(cid)
        current_chars += est
    if current:
        chunks.append(current)
    return chunks


def _optional_config_hints(gtest_state: dict[str, Any]) -> str:
    cache = gtest_state.get("project_code_config_cache") or {}
    rules = str(cache.get("code_rules.md") or "").strip()
    if not rules or len(rules) < 40:
        return ""
    return f"Optional project coding rules (hints only — follow exemplar first):\n{rules[:4000]}\n\n"


def build_exemplar_batch_prompt(
    exemplar: dict[str, Any],
    target_rows: list[dict[str, Any]],
    *,
    engineer_note: str = "",
    scope_label: str = "",
    import_group_label: str = "",
) -> str:
    ex_id = str(exemplar.get("candidate_id") or "")
    ex_code = str(exemplar.get("generated_code") or "")[:10_000]
    sample = str(exemplar.get("sample_snippet") or "")[:6000]
    style_notes = str(exemplar.get("style_notes") or "")

    targets_block: list[str] = []
    for row in target_rows:
        cid = str(row.get("candidate_id") or "")
        targets_block.append(
            f"testcase_id: {cid}\n"
            f"Before (expected_input):\n{str(row.get('expected_input') or '').strip()[:2500]}\n"
            f"After (expected_output):\n{str(row.get('expected_output') or '').strip()[:2500]}\n"
        )

    note = str(engineer_note or "").strip()
    note_block = f"Engineer note:\n{note[:2000]}\n\n" if note else ""
    sample_block = ""
    if sample:
        sample_block = f"Sample .cpp context (style reference):\n```cpp\n{sample}\n```\n\n"

    grouping_bits = [
        "Generate code for the following testcase rows from the selected existing group. "
        "Do not change grouping or infer extra testcase.",
    ]
    if scope_label:
        grouping_bits.append(f"Selection: {scope_label}.")
    if import_group_label:
        grouping_bits.append(f"Import Test Group: {import_group_label}.")
    grouping_bits.append(
        "The exemplar below is a coding-style reference only — do not add testcase_ids outside this list."
    )
    grouping_block = " ".join(grouping_bits) + "\n\n"

    return (
        "You are Microsoft 365 Copilot writing Google Test C++ for automotive ALEX.\n"
        f"{grouping_block}"
        "Rules (mandatory):\n"
        "- Follow the exemplar code style EXACTLY (fixture, mocks, helpers, comment layout).\n"
        "- Do NOT invent new helper APIs, macros, or patterns not shown in the exemplar or sample .cpp.\n"
        "- Use the same fixture and mock style as the exemplar.\n"
        "- Preserve testcase_id in spec comments (e.g. // TC_PM_004 …).\n"
        "- Generate exactly ONE TEST_F (or TEST) per target testcase.\n"
        "- Map Given:/When: from expected_input; Then: from expected_output.\n"
        "- No TODO, no placeholders.\n\n"
        f"{note_block}"
        f"Exemplar testcase_id: {ex_id}\n"
        f"Exemplar Before:\n{str(exemplar.get('expected_input') or '')[:3000]}\n\n"
        f"Exemplar After:\n{str(exemplar.get('expected_output') or '')[:3000]}\n\n"
        f"Exemplar generated code (COPY STYLE — do not copy signal values/logic):\n```cpp\n{ex_code}\n```\n\n"
        f"Style notes: {style_notes or '—'}\n\n"
        f"{sample_block}"
        f"Target testcases ({len(target_rows)}):\n"
        + "\n---\n".join(targets_block)
        + "\n\nRequired output format:\n"
        "[TESTCASE_CODE]\n"
        "For each target testcase, output exactly:\n"
        "testcase_id: <id>\n"
        "```cpp\n"
        "<complete spec comments + TEST_F for that testcase only>\n"
        "```\n\n"
        "[ASSUMPTIONS]\n"
        "- bullet list (max 8 lines, shared or per-batch)\n\n"
        "[UNRESOLVED]\n"
        "- list testcase_id values you could not complete, or write \"none\"\n"
    )


def build_exemplar_batch_prompts(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    engineer_note: str = "",
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
) -> dict[str, Any]:
    exemplar = get_code_exemplar(gtest_state)
    if not exemplar:
        return {"ok": False, "error": "Mark an exemplar testcase first."}

    from web.batch_target_resolution import resolve_batch_targets
    from web.copilot_batch_codegen import _batch_scope_label

    ex_id = str(exemplar.get("candidate_id") or "")
    resolved = resolve_batch_targets(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        language=language,
        scope=scope,
        group_key=group_key,
        group_field=group_field,
        exclude_candidate_ids=[ex_id] if ex_id else None,
    )
    if not resolved.get("ok"):
        return {"ok": False, "error": resolved.get("error") or "No target testcases in current selection."}
    targets = list(resolved.get("candidate_ids") or [])

    row_by_id = {
        str(r.get("candidate_id") or ""): r
        for r in resolved.get("ordered_rows") or []
        if r.get("candidate_id")
    }
    chunks = _chunk_targets(targets, row_by_id)
    import_group = str(resolved.get("group_key") or group_key or exemplar.get("import_group") or "").strip()
    scope_label = _batch_scope_label(scope, import_group)
    exemplar_group_hint = str(exemplar.get("import_group") or exemplar.get("test_group") or "").strip()

    prompts: list[dict[str, Any]] = []
    config_hints = _optional_config_hints(gtest_state)
    for i, chunk in enumerate(chunks):
        rows = [row_by_id[c] for c in chunk if c in row_by_id]
        prompt = build_exemplar_batch_prompt(
            exemplar,
            rows,
            engineer_note=engineer_note,
            scope_label=scope_label,
            import_group_label=import_group,
        )
        if config_hints:
            prompt = config_hints + prompt
        prompts.append(
            {
                "batch_index": i + 1,
                "batch_count": len(chunks),
                "candidate_ids": chunk,
                "testcase_count": len(chunk),
                "prompt": prompt,
                "char_count": len(prompt),
            }
        )
    combined = "\n\n--- BATCH ---\n\n".join(p["prompt"] for p in prompts) if len(prompts) > 1 else (prompts[0]["prompt"] if prompts else "")
    return {
        "ok": True,
        "exemplar_id": exemplar.get("candidate_id"),
        "exemplar_import_group": exemplar_group_hint,
        "target_count": len(targets),
        "scope": str(scope or "filter"),
        "group_key": import_group,
        "batch_count": len(prompts),
        "prompts": prompts,
        "combined_prompt": combined,
    }


def parse_exemplar_batch_response(text: str) -> dict[str, Any]:
    return parse_copilot_batch_response(text)


def apply_exemplar_batch_import(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    *,
    content: str,
    expected_candidate_ids: list[str] | None = None,
    language: str = "EN",
    generation_source: str = "EXEMPLAR_BATCH",
) -> dict[str, Any]:
    return apply_copilot_batch_import(
        bundle,
        gtest_state,
        job_output,
        content=content,
        expected_candidate_ids=expected_candidate_ids,
        language=language,
        generation_source=generation_source,
    )


def run_exemplar_batch_api(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    *,
    cfg: dict[str, Any],
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    engineer_note: str = "",
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
    progress_callback: Any | None = None,
    cancel_check: Any | None = None,
) -> dict[str, Any]:
    built = build_exemplar_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        language=language,
        engineer_note=engineer_note,
        scope=scope,
        group_key=group_key,
        group_field=group_field,
    )
    if not built.get("ok"):
        return built

    all_results: list[dict[str, Any]] = []
    total_saved = total_review = total_error = 0
    prompts = built.get("prompts") or []

    for idx, batch in enumerate(prompts):
        if cancel_check and cancel_check():
            break
        if progress_callback:
            progress_callback(
                idx,
                len(prompts),
                f"Exemplar API batch {idx + 1}/{len(prompts)} ({batch.get('testcase_count')} TCs)…",
            )
        chat = run_copilot_chat_result(
            cfg,
            str(batch.get("prompt") or ""),
            reuse_session_conversation=idx > 0,
        )
        if not chat.get("ok"):
            msg = str(chat.get("error") or "M365 API failed")
            for cid in batch.get("candidate_ids") or []:
                persist_batch_generation_error(
                    gtest_state, candidate_id=cid, error_message=msg, generation_source="EXEMPLAR_BATCH"
                )
                all_results.append(
                    {
                        "candidate_id": cid,
                        "ok": False,
                        "workflow_status": "ERROR",
                        "workflow_message": msg,
                        "code_status": "ERROR",
                    }
                )
                total_error += 1
            continue

        raw = str(chat.get("content") or chat.get("text") or "")
        one = apply_exemplar_batch_import(
            bundle,
            gtest_state,
            job_output,
            content=raw,
            expected_candidate_ids=batch.get("candidate_ids"),
            language=language,
            generation_source="EXEMPLAR_BATCH",
        )
        for r in one.get("results") or []:
            all_results.append(r)
        s = one.get("summary") or {}
        total_saved += int(s.get("saved") or 0)
        total_review += int(s.get("needs_review") or 0)
        total_error += int(s.get("error") or 0)

    summary = {
        "saved": total_saved,
        "needs_review": total_review,
        "error": total_error,
        "skipped": 0,
        "total": built.get("target_count") or len(all_results),
    }
    return {
        "ok": total_saved > 0 or total_review > 0,
        "batch_count": len(prompts),
        "results": all_results,
        "summary": summary,
        "exemplar_id": built.get("exemplar_id"),
    }
