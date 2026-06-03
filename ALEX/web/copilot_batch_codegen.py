"""Copilot-first batch GTest generation — orchestrate context, prompts, parse, save."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from web.code_style_samples import load_code_style_samples
from web.copilot_code_writer import parse_copilot_cpp_response
from web.gtest_workspace import (
    _workbench_row_for_candidate,
    persist_batch_generation_error,
    persist_generated_draft_workflow,
)
from web.m365_copilot import run_copilot_chat_result

_BATCH_MAX_PROMPT_CHARS = 30_000
_BATCH_TARGET_CHARS = 1_350
_DEFAULT_BATCH_SIZE = 1
_ALLOWED_BATCH_SIZES = (1, 5, 10, 20)
_SLIM_PROMPT_BUDGET = 18_000
_FULL_PROMPT_BUDGET = 26_000

_TESTCASE_CODE_SECTION_RE = re.compile(
    r"\[TESTCASE_CODE\](.*?)(?=\[ASSUMPTIONS\]|\[UNRESOLVED\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_ASSUMPTIONS_SECTION_RE = re.compile(
    r"\[ASSUMPTIONS\](.*?)(?=\[UNRESOLVED\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_UNRESOLVED_SECTION_RE = re.compile(r"\[UNRESOLVED\](.*)$", re.IGNORECASE | re.DOTALL)
_BLOCK_RE = re.compile(
    r"testcase_id\s*:\s*([A-Za-z0-9_]+)\s*(?:\n\s*)?```(?:cpp|c\+\+)?\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)
_TEST_F_RE = re.compile(r"TEST_F\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,", re.I)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_batch_size(size: int | None) -> int:
    n = int(size or _DEFAULT_BATCH_SIZE)
    if n in _ALLOWED_BATCH_SIZES:
        return n
    if n <= 1:
        return 1
    if n <= 5:
        return 5
    if n <= 10:
        return 10
    return 20


def _positive_limit(value: int | None, default: int) -> int:
    try:
        n = int(value or default)
    except (TypeError, ValueError):
        return default
    return max(4000, min(n, _FULL_PROMPT_BUDGET))


def _clip(text: Any, limit: int) -> str:
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "\n...[trimmed for Copilot latency]"


def _budget_join(
    *,
    required_parts: list[str],
    optional_parts: list[tuple[str, str]],
    tail_parts: list[str],
    budget: int,
) -> str:
    """Keep mandatory rules/targets/output intact; drop optional context first."""
    required = "".join(p for p in required_parts if p)
    tail = "".join(p for p in tail_parts if p)
    remaining = max(budget - len(required) - len(tail), 0)
    selected: list[str] = []
    for label, part in optional_parts:
        if not part:
            continue
        if len(part) <= remaining:
            selected.append(part)
            remaining -= len(part)
        elif remaining > 800:
            selected.append(f"{label}\n{_clip(part, remaining)}\n")
            remaining = 0
            break
    prompt = required + "".join(selected) + tail
    if len(prompt) <= budget:
        return prompt
    head_budget = max(budget - len(tail), 4000)
    return _clip(required + "".join(selected), head_budget) + "\n\n" + tail


def _draft_full_snippet(draft: dict[str, Any]) -> str:
    full = str(draft.get("full_snippet") or "").strip()
    if full:
        return full
    spec = str(draft.get("spec_comment_block") or "").strip()
    body = str(draft.get("code_body") or "").strip()
    if spec and body:
        return f"{spec}\n{body}".strip()
    return body


def get_code_exemplar(gtest_state: dict[str, Any]) -> dict[str, Any] | None:
    ex = gtest_state.get("code_exemplar")
    return ex if isinstance(ex, dict) and ex.get("candidate_id") else None


def _optional_config_hints(gtest_state: dict[str, Any], *, slim_prompt: bool = True) -> str:
    cache = gtest_state.get("project_code_config_cache") or {}
    rules = str(cache.get("code_rules.md") or "").strip()
    if not rules or len(rules) < 40 or "Inferred" in rules[:200]:
        return ""
    limit = 1200 if slim_prompt else 3500
    return (
        "Optional internal hints (do not treat as strict rules — sample .cc style wins):\n"
        f"{_clip(rules, limit)}\n\n"
    )


def _project_instruction_block(gtest_state: dict[str, Any], *, slim_prompt: bool = True) -> str:
    cache = gtest_state.get("project_code_config_cache") or {}
    instr = str(cache.get("project_instruction.md") or "").strip()
    if not instr:
        return ""
    limit = 5000 if slim_prompt else 8000
    return f"Engineer project instruction (primary — follow this):\n{_clip(instr, limit)}\n\n"


def _bundle_spec_context(bundle: dict[str, Any], *, language: str = "EN") -> str:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    preview = build_customer_testspec_preview(bundle, language=language)
    rows = preview.get("rows") or []
    layout = bundle.get("testspec_layout") or {}
    module = str(layout.get("module_name") or bundle.get("module_name") or "project").strip()
    groups: list[str] = []
    seen: set[str] = set()
    for row in rows:
        g = str(row.get("test_group") or "").strip()
        if g and g not in seen:
            seen.add(g)
            groups.append(g)
    lines = [
        f"Module: {module}",
        f"Imported testcase count: {len(rows)}",
    ]
    if groups:
        lines.append(f"Import Test Groups ({len(groups)}): " + ", ".join(groups[:24]))
    refs = bundle.get("code_references") or []
    if refs:
        files = [str(r.get("file") or r.get("path") or "") for r in refs[:12] if isinstance(r, dict)]
        files = [f for f in files if f]
        if files:
            lines.append("Project code references: " + ", ".join(files))
    return "\n".join(lines) + "\n\n"


def collect_copilot_project_context(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    language: str = "EN",
    slim_prompt: bool = True,
) -> dict[str, Any]:
    """Gather style/context from samples, drafts, exemplar, references — no YAML required."""
    samples = load_code_style_samples(bundle)
    sample_blocks: list[dict[str, str]] = []
    sample_limit = 1 if slim_prompt else 3
    sample_chars = 3200 if slim_prompt else 10_000
    for row in samples[:sample_limit]:
        snip = str(row.get("snippet") or "").strip()
        if snip:
            sample_blocks.append(
                {
                    "label": str(row.get("label") or row.get("source_file") or "sample.cc"),
                    "snippet": _clip(snip, sample_chars),
                }
            )

    saved_examples: list[dict[str, str]] = []
    saved_limit = 1 if slim_prompt else 2
    saved_chars = 2500 if slim_prompt else 6000
    for cid, draft in (gtest_state.get("drafts") or {}).items():
        if not isinstance(draft, dict):
            continue
        code = _draft_full_snippet(draft)
        if str(draft.get("code_status") or "").upper() == "SAVED" and re.search(r"\bTEST(?:_F)?\s*\(", code):
            saved_examples.append({"candidate_id": str(cid), "code": _clip(code, saved_chars)})
        if len(saved_examples) >= saved_limit:
            break

    exemplar = get_code_exemplar(gtest_state)
    ref_snippets: list[str] = []
    ref_limit = 1 if slim_prompt else 2
    ref_chars = 1200 if slim_prompt else 4000
    for ref in (bundle.get("code_references") or [])[:ref_limit]:
        if not isinstance(ref, dict):
            continue
        prev = str(ref.get("snippet_preview") or "")
        if prev:
            ref_snippets.append(_clip(prev, ref_chars))
        for block in (ref.get("test_blocks") or [])[: (1 if slim_prompt else 2)]:
            sn = str(block.get("snippet") or block.get("code_body") or "")
            if sn:
                ref_snippets.append(_clip(sn, ref_chars))

    folder_notes: list[str] = []
    for ref in bundle.get("code_references") or []:
        if isinstance(ref, dict) and ref.get("file"):
            folder_notes.append(str(ref.get("file")))

    return {
        "sample_blocks": sample_blocks,
        "saved_examples": saved_examples,
        "exemplar": exemplar,
        "reference_snippets": ref_snippets[: (1 if slim_prompt else 4)],
        "folder_files": folder_notes[: (12 if slim_prompt else 30)],
        "project_instruction": _project_instruction_block(gtest_state, slim_prompt=slim_prompt),
        "spec_context": _bundle_spec_context(bundle, language=language),
        "config_hints": _optional_config_hints(gtest_state, slim_prompt=slim_prompt),
        "language": language,
        "slim_prompt": bool(slim_prompt),
    }


def resolve_copilot_batch_targets(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    skip_saved: bool = False,
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
    exclude_candidate_ids: list[str] | None = None,
) -> list[str]:
    from web.batch_target_resolution import resolve_batch_targets

    resolved = resolve_batch_targets(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        language=language,
        scope=scope,
        group_key=group_key,
        group_field=group_field,
        exclude_candidate_ids=exclude_candidate_ids,
        skip_saved=skip_saved,
    )
    return list(resolved.get("candidate_ids") or [])


def _chunk_targets(
    target_ids: list[str],
    row_by_id: dict[str, dict[str, Any]],
    batch_size: int,
) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for cid in target_ids:
        row = row_by_id.get(cid) or {}
        est = _BATCH_TARGET_CHARS + len(str(row.get("expected_input") or "")) + len(
            str(row.get("expected_output") or "")
        )
        if current and (len(current) >= batch_size or current_chars + est > _BATCH_MAX_PROMPT_CHARS):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(cid)
        current_chars += est
    if current:
        chunks.append(current)
    return chunks


def build_copilot_batch_prompt(
    context: dict[str, Any],
    target_rows: list[dict[str, Any]],
    *,
    engineer_note: str = "",
    scope_label: str = "",
    import_group_label: str = "",
    slim_prompt: bool = True,
    prompt_budget: int | None = None,
) -> str:
    budget = _positive_limit(prompt_budget, _SLIM_PROMPT_BUDGET if slim_prompt else _FULL_PROMPT_BUDGET)
    samples_text = ""
    for block in context.get("sample_blocks") or []:
        samples_text += f"\n### {block['label']}\n```cpp\n{block['snippet']}\n```\n"

    saved_text = ""
    for ex in context.get("saved_examples") or []:
        saved_text += f"\n### Saved example {ex['candidate_id']}\n```cpp\n{ex['code']}\n```\n"

    exemplar = context.get("exemplar")
    exemplar_block = ""
    if exemplar and exemplar.get("generated_code"):
        exemplar_code_chars = 2500 if slim_prompt else 9000
        exemplar_io_chars = 900 if slim_prompt else 2500
        exemplar_block = (
            f"Accepted exemplar testcase_id: {exemplar.get('candidate_id')}\n"
            f"Before:\n{_clip(exemplar.get('expected_input'), exemplar_io_chars)}\n"
            f"After:\n{_clip(exemplar.get('expected_output'), exemplar_io_chars)}\n"
            f"```cpp\n{_clip(exemplar.get('generated_code'), exemplar_code_chars)}\n```\n\n"
        )

    refs = context.get("reference_snippets") or []
    ref_block = ""
    if refs:
        ref_block = "Additional project GTest snippets:\n" + "\n---\n".join(
            f"```cpp\n{r}\n```" for r in refs[:2]
        ) + "\n\n"

    folder_files = context.get("folder_files") or []
    folder_block = ""
    if folder_files:
        folder_block = "Project code files (context): " + ", ".join(folder_files[: (12 if slim_prompt else 20)]) + "\n\n"

    targets_block: list[str] = []
    target_chars = 1600 if slim_prompt else 2800
    for row in target_rows:
        cid = str(row.get("candidate_id") or "")
        event = str(row.get("event") or row.get("test_function") or "").strip()
        targets_block.append(
            f"testcase_id: {cid}\n"
            f"event: {event}\n"
            f"Before (expected_input):\n{_clip(row.get('expected_input'), target_chars)}\n"
            f"After (expected_output):\n{_clip(row.get('expected_output'), target_chars)}\n"
        )

    instruction = str(engineer_note or "").strip()
    instruction_chars = 6000 if slim_prompt else 12_000
    instruction_block = (
        "Project instruction markdown from current editor (primary generation rules — follow exactly):\n"
        f"{_clip(instruction, instruction_chars)}\n\n"
        if instruction
        else ""
    )
    stored_instruction_block = "" if instruction_block else str(context.get("project_instruction") or "")

    scope_bits = [
        "Use the imported testcase group/order exactly as provided. "
        "Do not change grouping; do not regroup testcase, reorder testcase, or infer extra testcase.",
    ]
    if scope_label:
        scope_bits.append(f"Selection: {scope_label}.")
    if import_group_label:
        scope_bits.append(f"Import Test Group: {import_group_label}.")
    scope_bits.append(
        "Exemplar or saved examples are coding-style references only — do not add testcase_ids "
        "outside this list."
    )
    grouping_block = " ".join(scope_bits) + "\n\n"

    required_head = (
        "You are Microsoft 365 Copilot generating Google Test C++ for automotive ALEX.\n"
        "ALEX is a Copilot orchestrator — use testcase rows + sample code; do NOT invent new helper APIs.\n\n"
        f"{grouping_block}"
        "Rules (mandatory):\n"
        "- Follow sample .cc / project GTest style EXACTLY (fixture, EXPECT_CALL, timing, comments).\n"
        "- Generate only the testcase IDs listed below.\n"
        "- Return code mapped exactly to testcase_id.\n"
        "- One TEST_F (or TEST) per testcase_id.\n"
        "- Spec comment must include testcase_id (e.g. // TC_PM_004 …).\n"
        "- Map Given:/When: from expected_input; Then: from expected_output.\n"
        "- If uncertain, return UNRESOLVED instead of inventing code.\n"
        "- No TODO, no placeholders.\n\n"
        f"{instruction_block}"
        f"{stored_instruction_block}"
        f"{context.get('spec_context') or ''}"
        f"{folder_block}"
    )
    optional_parts = [
        ("Optional internal hints:\n", str(context.get("config_hints") or "")),
        ("Primary sample .cc (style anchor):\n", f"Primary sample .cc (style anchor):\n{samples_text}\n" if samples_text else ""),
        ("Saved examples:\n", saved_text),
        ("Accepted exemplar:\n", exemplar_block),
        ("Additional project GTest snippets:\n", ref_block),
    ]
    tail = (
        f"Selected testcase IDs ({len(target_rows)}):\n"
        + "\n---\n".join(targets_block)
        + "\n\nRequired output format:\n"
        "[TESTCASE_CODE]\n"
        "testcase_id: <id>\n"
        "```cpp\n"
        "<full spec comments + TEST_F for that testcase only>\n"
        "```\n"
        "(repeat for each completed testcase)\n\n"
        "[UNRESOLVED]\n"
        "testcase_id: <id>\n"
        "reason: <short reason>\n"
        "(or write \"none\")\n\n"
        "[ASSUMPTIONS]\n"
        "- bullet list (max 8 lines)\n"
    )
    return _budget_join(
        required_parts=[required_head],
        optional_parts=optional_parts,
        tail_parts=[tail],
        budget=budget,
    )


def _batch_scope_label(scope: str, group_key: str) -> str:
    s = str(scope or "filter").strip().lower()
    if s == "all":
        return "all imported testcases (Excel order)"
    if s == "group" and group_key:
        return f"current import group ({group_key})"
    if s == "selected":
        return "selected testcase row(s)"
    return "current UI filter"


def build_copilot_batch_prompts(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    engineer_note: str = "",
    batch_size: int | None = None,
    skip_saved: bool = False,
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
    exclude_candidate_ids: list[str] | None = None,
    allow_missing_sample: bool = False,
    slim_prompt: bool = True,
    prompt_budget: int | None = None,
) -> dict[str, Any]:
    context = collect_copilot_project_context(bundle, gtest_state, language=language, slim_prompt=slim_prompt)
    if (
        not allow_missing_sample
        and not context.get("sample_blocks")
        and not context.get("saved_examples")
        and not context.get("exemplar")
    ):
        return {
            "ok": False,
            "error": "Load sample .cc or save at least one good testcase before Generate All with Copilot API.",
        }

    from web.batch_target_resolution import resolve_batch_targets

    bs = _normalize_batch_size(batch_size)
    resolved = resolve_batch_targets(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        language=language,
        scope=scope,
        group_key=group_key,
        group_field=group_field,
        exclude_candidate_ids=exclude_candidate_ids,
        skip_saved=skip_saved,
    )
    if not resolved.get("ok"):
        return {"ok": False, "error": resolved.get("error") or "No target testcases in current selection."}
    targets = list(resolved.get("candidate_ids") or [])

    row_by_id = {
        str(r.get("candidate_id") or ""): r
        for r in resolved.get("ordered_rows") or []
        if r.get("candidate_id")
    }
    chunks = _chunk_targets(targets, row_by_id, bs)
    scope_label = _batch_scope_label(scope, str(resolved.get("group_key") or group_key or ""))
    import_group = str(resolved.get("group_key") or group_key or "").strip()

    prompts: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        rows = [row_by_id[c] for c in chunk if c in row_by_id]
        prompt = build_copilot_batch_prompt(
            context,
            rows,
            engineer_note=engineer_note,
            scope_label=scope_label,
            import_group_label=import_group,
            slim_prompt=slim_prompt,
            prompt_budget=prompt_budget,
        )
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
    combined = (
        "\n\n--- BATCH ---\n\n".join(p["prompt"] for p in prompts)
        if len(prompts) > 1
        else (prompts[0]["prompt"] if prompts else "")
    )
    return {
        "ok": True,
        "target_count": len(targets),
        "scope": str(scope or "filter"),
        "group_key": import_group,
        "batch_size": bs,
        "batch_count": len(prompts),
        "prompts": prompts,
        "combined_prompt": combined,
        "context_summary": {
            "samples": len(context.get("sample_blocks") or []),
            "saved_examples": len(context.get("saved_examples") or []),
            "has_exemplar": bool(context.get("exemplar")),
            "reference_snippets": len(context.get("reference_snippets") or []),
            "slim_prompt": bool(slim_prompt),
            "prompt_budget": _positive_limit(
                prompt_budget, _SLIM_PROMPT_BUDGET if slim_prompt else _FULL_PROMPT_BUDGET
            ),
            "max_prompt_chars": max([int(p.get("char_count") or 0) for p in prompts] or [0]),
        },
    }


def _parse_unresolved_map(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current: str | None = None
    for line in block.splitlines():
        m_id = re.match(r"testcase_id\s*:\s*([A-Za-z0-9_]+)", line.strip(), re.I)
        if m_id:
            current = m_id.group(1)
            out.setdefault(current, "marked unresolved by Copilot")
            continue
        m_reason = re.match(r"reason\s*:\s*(.+)", line.strip(), re.I)
        if m_reason and current:
            out[current] = m_reason.group(1).strip()
    return out


def parse_copilot_batch_response(text: str) -> dict[str, Any]:
    """Parse [TESTCASE_CODE] / [UNRESOLVED] / [ASSUMPTIONS] batch Copilot output."""
    raw = str(text or "").strip()
    if not raw:
        return {
            "ok": False,
            "error": "empty response",
            "items": [],
            "assumptions": [],
            "unresolved": [],
            "unresolved_by_id": {},
        }

    body = raw
    m_sec = _TESTCASE_CODE_SECTION_RE.search(raw)
    if m_sec:
        body = m_sec.group(1)

    assumptions: list[str] = []
    m_a = _ASSUMPTIONS_SECTION_RE.search(raw)
    if m_a:
        for line in m_a.group(1).splitlines():
            line = re.sub(r"^[\s\-*•]+", "", line.strip())
            if line:
                assumptions.append(line)

    unresolved_by_id: dict[str, str] = {}
    m_u = _UNRESOLVED_SECTION_RE.search(raw)
    if m_u:
        block = m_u.group(1).strip()
        if block.lower() not in ("none", "n/a", "—", "-", "none."):
            unresolved_by_id = _parse_unresolved_map(block)

    items: list[dict[str, Any]] = []
    for m in _BLOCK_RE.finditer(body):
        cid = m.group(1).strip()
        cpp = m.group(2).strip()
        parsed = parse_copilot_cpp_response(f"```cpp\n{cpp}\n```")
        full = parsed.get("full_snippet") or cpp
        items.append(
            {
                "candidate_id": cid,
                "full_snippet": full,
                "spec_comment_block": parsed.get("spec_comment_block") or "",
                "code_body": parsed.get("code_body") or "",
            }
        )

    if not items:
        fence_re = re.compile(r"```(?:cpp|c\+\+)?\s*\n?([\s\S]*?)```", re.IGNORECASE)
        for m in fence_re.finditer(body):
            cpp = m.group(1).strip()
            prefix = body[max(0, m.start() - 200) : m.start()]
            id_m = re.search(r"testcase_id\s*:\s*([A-Za-z0-9_]+)", prefix, re.I)
            cid = id_m.group(1) if id_m else ""
            if not cid:
                cm = re.search(r"//\s*(@alex:begin\s+)?([A-Za-z0-9_]+)", cpp)
                cid = cm.group(2) if cm else ""
            if cid:
                parsed = parse_copilot_cpp_response(f"```cpp\n{cpp}\n```")
                items.append(
                    {
                        "candidate_id": cid,
                        "full_snippet": parsed.get("full_snippet") or cpp,
                        "spec_comment_block": parsed.get("spec_comment_block") or "",
                        "code_body": parsed.get("code_body") or "",
                    }
                )

    unresolved_list = [f"{k}: {v}" for k, v in unresolved_by_id.items()]
    return {
        "ok": bool(items) or bool(unresolved_by_id),
        "items": items,
        "assumptions": assumptions,
        "unresolved": unresolved_list,
        "unresolved_by_id": unresolved_by_id,
        "parsed_count": len(items),
    }


def apply_copilot_batch_import(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    *,
    content: str,
    expected_candidate_ids: list[str] | None = None,
    language: str = "EN",
    generation_source: str = "COPILOT_BATCH",
) -> dict[str, Any]:
    parsed = parse_copilot_batch_response(content)
    unresolved_by_id = dict(parsed.get("unresolved_by_id") or {})
    parsed_by_id = {str(i["candidate_id"]): i for i in parsed.get("items") or [] if i.get("candidate_id")}

    if not parsed_by_id and not unresolved_by_id:
        return {
            "ok": False,
            "error": parsed.get("error") or "No [TESTCASE_CODE] or [UNRESOLVED] blocks parsed.",
            "parse": parsed,
            "results": [],
            "summary": {"saved": 0, "needs_review": 0, "error": 0, "skipped": 0, "total": 0},
        }

    ctx = collect_copilot_project_context(bundle, gtest_state, language=language)
    sample_snippet = ""
    if ctx.get("sample_blocks"):
        sample_snippet = ctx["sample_blocks"][0].get("snippet") or ""
    elif ctx.get("exemplar"):
        sample_snippet = str(ctx["exemplar"].get("sample_snippet") or "")

    cfg_cache = gtest_state.get("project_code_config_cache") or {}
    code_rules = str(cfg_cache.get("code_rules.md") or "")
    api_catalog = str(cfg_cache.get("api_catalog.yaml") or "")

    expected = set(expected_candidate_ids or [])
    target_ids = list(expected) if expected else list(set(parsed_by_id) | set(unresolved_by_id))

    results: list[dict[str, Any]] = []
    saved = needs_review = error = skipped = 0

    for cid in target_ids:
        if cid in unresolved_by_id:
            msg = f"unresolved: {unresolved_by_id[cid]}"
            persist_batch_generation_error(
                gtest_state, candidate_id=cid, error_message=msg, generation_source=generation_source
            )
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                }
            )
            error += 1
            continue

        if cid not in parsed_by_id:
            msg = "testcase_id not found in Copilot API chunk output"
            persist_batch_generation_error(
                gtest_state, candidate_id=cid, error_message=msg, generation_source=generation_source
            )
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                }
            )
            error += 1
            continue

        item = parsed_by_id[cid]
        full = str(item.get("full_snippet") or "").strip()
        if not full or not re.search(r"\bTEST(?:_F)?\s*\(", full):
            msg = "parse failed — no TEST_F in block"
            persist_batch_generation_error(
                gtest_state, candidate_id=cid, error_message=msg, generation_source=generation_source
            )
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                }
            )
            error += 1
            continue

        wf = persist_generated_draft_workflow(
            bundle,
            gtest_state,
            candidate_id=cid,
            draft_payload={
                "full_snippet": full,
                "spec_comment_block": item.get("spec_comment_block") or "",
                "code_body": item.get("code_body") or "",
                "source_kind": "copilot_batch",
            },
            generation_source=generation_source,
            language=language,
            sample_snippet=sample_snippet,
            code_rules_md=code_rules,
            api_catalog_yaml=api_catalog,
            persist=True,
        )
        st = str(wf.get("workflow_status") or wf.get("code_status") or "ERROR")
        if st == "SAVED":
            saved += 1
        elif st == "NEEDS_REVIEW":
            needs_review += 1
        else:
            error += 1
        results.append(
            {
                "candidate_id": cid,
                "ok": st == "SAVED",
                "workflow_status": st,
                "workflow_message": wf.get("workflow_message") or "",
                "code_status": wf.get("code_status") or st,
                "generation_source": generation_source,
            }
        )

    for cid in parsed_by_id:
        if expected and cid not in expected:
            skipped += 1
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "skipped": True,
                    "workflow_status": "skipped",
                    "workflow_message": "parsed but not in target list",
                }
            )

    gtest_state.setdefault("copilot_batch", {})["last_import"] = {
        "at": _now_iso(),
        "parsed_count": parsed.get("parsed_count"),
        "unresolved_count": len(unresolved_by_id),
        "assumptions": parsed.get("assumptions"),
    }
    gtest_state.setdefault("copilot_batch", {})["last_results"] = results

    summary = {
        "saved": saved,
        "needs_review": needs_review,
        "error": error,
        "skipped": skipped,
        "total": len(target_ids),
    }
    return {
        "ok": saved > 0 or needs_review > 0,
        "parse": parsed,
        "results": results,
        "summary": summary,
    }


def run_copilot_batch_api(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    job_output: Any,
    *,
    cfg: dict[str, Any],
    candidate_ids: list[str] | None = None,
    language: str = "EN",
    engineer_note: str = "",
    batch_size: int | None = None,
    skip_saved: bool = False,
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
    exclude_candidate_ids: list[str] | None = None,
    progress_callback: Any | None = None,
    cancel_check: Any | None = None,
    retry_count: int = 0,
    allow_missing_sample: bool = False,
    user_id: str | None = None,
    slim_prompt: bool = True,
    prompt_budget: int | None = None,
) -> dict[str, Any]:
    built = build_copilot_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        language=language,
        engineer_note=engineer_note,
        batch_size=batch_size,
        skip_saved=skip_saved,
        scope=scope,
        group_key=group_key,
        group_field=group_field,
        exclude_candidate_ids=exclude_candidate_ids,
        allow_missing_sample=allow_missing_sample,
        slim_prompt=slim_prompt,
        prompt_budget=prompt_budget,
    )
    if not built.get("ok"):
        return built

    all_results: list[dict[str, Any]] = []
    total_saved = total_review = total_error = 0
    prompts = built.get("prompts") or []

    gtest_state.setdefault("copilot_batch", {})["run"] = {
        "status": "running",
        "batch_total": len(prompts),
        "batch_index": 0,
        "target_count": built.get("target_count") or 0,
        "queued_chunks": len(prompts),
        "running_chunk": 0,
        "completed_chunks": 0,
        "failed_chunks": 0,
        "failed_chunk_details": [],
        "failed_candidate_ids": [],
        "retry_count": int(retry_count or 0),
        "status_message": "Queued Copilot API chunks.",
        "saved": 0,
        "needs_review": 0,
        "error": 0,
    }

    for idx, batch in enumerate(prompts):
        if cancel_check and cancel_check():
            break
        run = gtest_state.setdefault("copilot_batch", {}).setdefault("run", {})
        run["batch_index"] = idx + 1
        run["running_chunk"] = idx + 1
        run["queued_chunks"] = max(len(prompts) - idx - 1, 0)
        run["completed_chunks"] = idx
        run["current_candidate_ids"] = list(batch.get("candidate_ids") or [])
        run["status_message"] = f"Running Copilot API chunk {idx + 1}/{len(prompts)}."
        if progress_callback:
            progress_callback(
                idx,
                len(prompts),
                f"Copilot API chunk {idx + 1}/{len(prompts)} ({batch.get('testcase_count')} TCs)…",
                saved=total_saved,
                needs_review=total_review,
                error=total_error,
                target_count=built.get("target_count") or 0,
                current_candidate_ids=list(batch.get("candidate_ids") or []),
                queued_chunks=run["queued_chunks"],
                running_chunk=run["running_chunk"],
                completed_chunks=run["completed_chunks"],
                failed_chunks=run.get("failed_chunks", 0),
                failed_chunk_details=run.get("failed_chunk_details", []),
                retry_count=run.get("retry_count", 0),
                status_message=run["status_message"],
            )
        response_started = perf_counter()
        chat = run_copilot_chat_result(
            cfg,
            str(batch.get("prompt") or ""),
            reuse_session_conversation=(idx > 0 and not slim_prompt),
            user_id=user_id,
        )
        run["last_response_s"] = round(perf_counter() - response_started, 1)
        if not chat.get("ok"):
            msg = str(chat.get("error") or "M365 API failed")
            failed_ids = list(batch.get("candidate_ids") or [])
            detail = {
                "batch_index": idx + 1,
                "candidate_ids": failed_ids,
                "reason": msg,
                "last_response_s": run.get("last_response_s"),
            }
            details = list(run.get("failed_chunk_details") or [])
            details.append(detail)
            run["failed_chunk_details"] = details
            run["failed_chunks"] = len(details)
            run["failed_candidate_ids"] = list(dict.fromkeys([*list(run.get("failed_candidate_ids") or []), *failed_ids]))
            run["failed_chunk_reason"] = msg
            run["completed_chunks"] = idx + 1
            run["status_message"] = f"Copilot API chunk {idx + 1}/{len(prompts)} failed: {msg}"
            for cid in batch.get("candidate_ids") or []:
                persist_batch_generation_error(
                    gtest_state, candidate_id=cid, error_message=msg, generation_source="COPILOT_BATCH"
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
            run["saved"] = total_saved
            run["needs_review"] = total_review
            run["error"] = total_error
            if progress_callback:
                progress_callback(
                    idx,
                    len(prompts),
                    run["status_message"],
                    saved=total_saved,
                    needs_review=total_review,
                    error=total_error,
                    target_count=built.get("target_count") or 0,
                    current_candidate_ids=failed_ids,
                    queued_chunks=run.get("queued_chunks", 0),
                    running_chunk=run.get("running_chunk", idx + 1),
                    completed_chunks=run.get("completed_chunks", idx + 1),
                    failed_chunks=run.get("failed_chunks", 0),
                    failed_chunk_details=run.get("failed_chunk_details", []),
                    failed_candidate_ids=run.get("failed_candidate_ids", []),
                    failed_chunk_reason=msg,
                    last_response_s=run.get("last_response_s"),
                    retry_count=run.get("retry_count", 0),
                    status_message=run["status_message"],
                )
            continue

        raw = str(chat.get("reply") or chat.get("content") or chat.get("text") or "")
        one = apply_copilot_batch_import(
            bundle,
            gtest_state,
            job_output,
            content=raw,
            expected_candidate_ids=batch.get("candidate_ids"),
            language=language,
            generation_source="COPILOT_BATCH",
        )
        for r in one.get("results") or []:
            all_results.append(r)
        s = one.get("summary") or {}
        total_saved += int(s.get("saved") or 0)
        total_review += int(s.get("needs_review") or 0)
        total_error += int(s.get("error") or 0)
        run = gtest_state.setdefault("copilot_batch", {}).setdefault("run", {})
        chunk_error_results = [
            r for r in (one.get("results") or [])
            if str(r.get("workflow_status") or r.get("code_status") or "").upper() == "ERROR"
        ]
        if chunk_error_results:
            failed_ids = [str(r.get("candidate_id") or "") for r in chunk_error_results if r.get("candidate_id")]
            reason = str(
                chunk_error_results[0].get("workflow_message")
                or chunk_error_results[0].get("error")
                or "Copilot response did not produce usable code for every testcase in this API chunk."
            )
            detail = {
                "batch_index": idx + 1,
                "candidate_ids": failed_ids,
                "reason": reason,
                "last_response_s": run.get("last_response_s"),
            }
            details = list(run.get("failed_chunk_details") or [])
            details.append(detail)
            run["failed_chunk_details"] = details
            run["failed_chunks"] = len(details)
            run["failed_candidate_ids"] = list(dict.fromkeys([*list(run.get("failed_candidate_ids") or []), *failed_ids]))
            run["failed_chunk_reason"] = reason
        run.update(
            {
                "saved": total_saved,
                "needs_review": total_review,
                "error": total_error,
                "batch_index": idx + 1,
                "completed_chunks": idx + 1,
                "queued_chunks": max(len(prompts) - idx - 1, 0),
                "status_message": f"Completed Copilot API chunk {idx + 1}/{len(prompts)}.",
            }
        )
        if progress_callback:
            progress_callback(
                idx,
                len(prompts),
                run["status_message"],
                saved=total_saved,
                needs_review=total_review,
                error=total_error,
                target_count=built.get("target_count") or 0,
                current_candidate_ids=list(batch.get("candidate_ids") or []),
                queued_chunks=run.get("queued_chunks", 0),
                running_chunk=run.get("running_chunk", idx + 1),
                completed_chunks=run.get("completed_chunks", idx + 1),
                failed_chunks=run.get("failed_chunks", 0),
                failed_chunk_details=run.get("failed_chunk_details", []),
                failed_candidate_ids=run.get("failed_candidate_ids", []),
                failed_chunk_reason=run.get("failed_chunk_reason", ""),
                last_response_s=run.get("last_response_s"),
                retry_count=run.get("retry_count", 0),
                status_message=run["status_message"],
            )

    run = gtest_state.setdefault("copilot_batch", {})["run"]
    run["status"] = "completed"
    run["running_chunk"] = 0
    run["queued_chunks"] = 0
    run["completed_chunks"] = len(prompts)
    run["status_message"] = (
        f"Completed with {run.get('failed_chunks', 0)} failed API chunk(s)."
        if run.get("failed_chunks")
        else "Completed all Copilot API chunks."
    )
    summary = {
        "saved": total_saved,
        "needs_review": total_review,
        "error": total_error,
        "skipped": 0,
        "total": built.get("target_count") or len(all_results),
    }
    ok = total_saved > 0 or total_review > 0
    failure_reason = ""
    if not ok:
        details = run.get("failed_chunk_details") or []
        if details:
            failure_reason = str(details[-1].get("reason") or "")
        failure_reason = failure_reason or str(run.get("failed_chunk_reason") or "")
        if not failure_reason and all_results:
            failure_reason = str(
                all_results[0].get("workflow_message")
                or all_results[0].get("error")
                or ""
            )
        failure_reason = failure_reason or "Copilot response did not contain usable [TESTCASE_CODE] or [UNRESOLVED] output."
    return {
        "ok": ok,
        "error": failure_reason if not ok else "",
        "error_category": "m365_copilot_batch" if not ok else "",
        "batch_count": len(prompts),
        "batch_size": built.get("batch_size"),
        "results": all_results,
        "summary": summary,
        "context_summary": built.get("context_summary"),
    }
