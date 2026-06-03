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
    flush_batch_run_checkpoint,
    persist_batch_generation_error,
    persist_generated_draft_workflow,
    save_draft,
)
from web.m365_copilot import run_copilot_chat_result

_BATCH_MAX_PROMPT_CHARS = 30_000
_BATCH_TARGET_CHARS = 1_350
_DEFAULT_BATCH_SIZE = 1
_ALLOWED_BATCH_SIZES = (1, 5, 10, 20)
_SLIM_PROMPT_BUDGET = 5_000
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


def _cpp_ident(value: str, fallback: str = "Generated") -> str:
    ident = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not ident:
        ident = fallback
    if ident[0].isdigit():
        ident = f"TC_{ident}"
    return ident


def _review_scaffold_code(row: dict[str, Any], reason: str) -> str:
    cid = str(row.get("candidate_id") or row.get("id") or "").strip()
    event = str(row.get("event") or row.get("test_function") or "").strip()
    test_name = _cpp_ident(cid or event, "GeneratedTestcase")
    before = _clip(row.get("expected_input"), 1800)
    after = _clip(row.get("expected_output"), 1800)
    reason_text = str(reason or "Copilot API did not return concrete code.").replace('"', "'")
    return (
        f"// {cid} {event}".rstrip() + "\n"
        "// NEEDS_REVIEW: Copilot API fallback scaffold. Replace with project-specific RTE/mock calls.\n"
        f"// Reason: {reason_text}\n"
        "//\n"
        "// Expected input:\n"
        + "\n".join(f"// {line}" for line in before.splitlines())
        + "\n//\n"
        "// Expected output:\n"
        + "\n".join(f"// {line}" for line in after.splitlines())
        + "\n"
        f"TEST(AlexGeneratedFallback, {test_name}) {{\n"
        f"  GTEST_SKIP() << \"NEEDS_REVIEW: {reason_text}\";\n"
        "}\n"
    )


def _persist_review_scaffold(
    gtest_state: dict[str, Any],
    *,
    row: dict[str, Any],
    reason: str,
    generation_source: str = "COPILOT_BATCH_FALLBACK",
) -> str:
    cid = str(row.get("candidate_id") or row.get("id") or "").strip()
    if not cid:
        return ""
    full = _review_scaffold_code(row, reason)
    body_start = re.search(r"\bTEST\s*\(", full)
    spec = full[: body_start.start()].strip() if body_start else ""
    body = full[body_start.start() :].strip() if body_start else full
    save_draft(
        gtest_state,
        draft_key=cid,
        draft={
            "full_snippet": full,
            "spec_comment_block": spec,
            "code_body": body,
            "code_status": "NEEDS_REVIEW",
            "workflow_message": "Copilot API fallback scaffold; review and replace project-specific calls.",
            "review_reason": reason,
            "generation_source": generation_source,
            "is_fallback_scaffold": True,
            "is_partial_code": False,
            "issue_reason": "fallback_scaffold_timeout",
            "fallback_reason": str(reason or "Copilot API did not return concrete code."),
        },
        engineer_edited=False,
        wrap_markers=True,
    )
    return full


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


def _testcode_memory_block(gtest_state: dict[str, Any], *, slim_prompt: bool = True) -> str:
    from web.project_testcode_memory import memory_for_prompt

    cache = gtest_state.get("project_code_config_cache") or {}
    mem = str(cache.get("project_testcode_memory.md") or "").strip()
    if not mem:
        return ""
    limit = 3000 if slim_prompt else 5000
    clipped = memory_for_prompt(mem, char_limit=limit)
    if not clipped:
        return ""
    return (
        "Project Test Code Memory (primary style/reference — use this first):\n"
        f"{clipped}\n\n"
    )


def _style_example_score(snippet: str) -> int:
    """Score a code snippet by how representative it is of the real project style."""
    s = 0
    if re.search(r"/\*\*", snippet):
        s += 1
    if re.search(r"[぀-ヿ一-鿿]", snippet):
        s += 3  # Japanese content = strong project style signal
    if "EXPECT_CALL" in snippet:
        s += 2
    if "Rte_Read" in snippet:
        s += 2
    if "igsw_Main_Run" in snippet:
        s += 2
    if "EXPECT_THAT" in snippet:
        s += 1
    if "EXPECT_EQ" in snippet:
        s += 1
    if "WillRepeatedly" in snippet:
        s += 1
    if "SetArgPointee" in snippet:
        s += 1
    if re.search(r"\bTEST_F\s*\(", snippet):
        s += 1
    # Penalise very short or very generic snippets
    if len(snippet) < 80:
        s -= 2
    return s


def pick_representative_style_example(
    samples: list[dict[str, Any]],
    *,
    slim_prompt: bool = True,
    char_limit: int | None = None,
) -> str:
    """Return the most representative TEST_F snippet from loaded samples.

    Prefers blocks with Japanese comments, EXPECT_CALL, Rte_Read, igsw_Main_Run,
    EXPECT_THAT — i.e. blocks that encode the real project coding style.
    """
    if not samples:
        return ""
    limit = char_limit if char_limit is not None else (2000 if slim_prompt else 5000)
    best = max(samples, key=lambda r: _style_example_score(str(r.get("snippet") or "")))
    snippet = str(best.get("snippet") or "").strip()
    if not snippet or not re.search(r"\bTEST(?:_F)?\s*\(", snippet):
        return ""
    return _clip(snippet, limit)


def build_style_example_block(snippet: str, label: str = "") -> str:
    """Format a representative snippet as a STYLE EXAMPLE section for the Copilot prompt."""
    if not snippet:
        return ""
    src = f" (from {label})" if label else ""
    return (
        f"━━━ STYLE EXAMPLE — FOLLOW THIS FORMAT{src} ━━━\n"
        "```cpp\n"
        f"{snippet.strip()}\n"
        "```\n\n"
        "Style rules (copy this structure):\n"
        "- Use the same block comment format (/** … */) with testcase description\n"
        "- Keep Japanese testcase comments exactly if present\n"
        "- Use Given / When / Then comment labels in the same positions\n"
        "- Use EXPECT_CALL + Rte_Read_<signal>(NotNull()) for input signal setup\n"
        "- Use WillRepeatedly(DoAll(SetArgPointee<0>(value), Return(RTE_E_OK)))\n"
        "- Use igsw_Main_Run() as the execution/cycle step\n"
        "- Use EXPECT_THAT(signal, Eq(value)) for output assertions\n"
        "- Do not replace this style with generic TODO_REVIEW unless the specific API is truly unknown\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )


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
    sample_chars = 700 if slim_prompt else 10_000
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
    saved_chars = 700 if slim_prompt else 6000
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
    ref_limit = 0 if slim_prompt else 2
    ref_chars = 0 if slim_prompt else 4000
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

    # Pick the best representative TEST_F block for the style example section
    all_sample_rows = samples  # already loaded above
    style_snippet = pick_representative_style_example(all_sample_rows, slim_prompt=slim_prompt)
    if not style_snippet and exemplar and exemplar.get("generated_code"):
        # Fall back to accepted exemplar if no loaded sample
        ex_code = str(exemplar.get("generated_code") or "").strip()
        if re.search(r"\bTEST(?:_F)?\s*\(", ex_code):
            style_snippet = _clip(ex_code, 2000 if slim_prompt else 5000)
    if not style_snippet:
        # Fall back to first saved SAVED example
        for _, d in (gtest_state.get("drafts") or {}).items():
            if isinstance(d, dict) and str(d.get("code_status") or "").upper() == "SAVED":
                code = _draft_full_snippet(d)
                if re.search(r"\bTEST(?:_F)?\s*\(", code):
                    style_snippet = _clip(code, 2000 if slim_prompt else 5000)
                    break
    style_label = ""
    if all_sample_rows:
        best_row = max(all_sample_rows, key=lambda r: _style_example_score(str(r.get("snippet") or "")))
        style_label = str(best_row.get("label") or best_row.get("source_file") or "")

    return {
        "sample_blocks": sample_blocks,
        "saved_examples": saved_examples,
        "exemplar": exemplar,
        "reference_snippets": ref_snippets[: (1 if slim_prompt else 4)],
        "folder_files": folder_notes[: (6 if slim_prompt else 30)],
        "testcode_memory": _testcode_memory_block(gtest_state, slim_prompt=slim_prompt),
        "style_example_snippet": style_snippet,
        "style_example_label": style_label,
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


def collect_retry_candidate_ids(
    gtest_state: dict[str, Any],
    bundle: dict[str, Any],
    *,
    language: str = "EN",
) -> list[str]:
    """Return IDs of testcases in NEEDS_REVIEW or ERROR state, in Excel import order.

    Used by the retry-failed endpoint so only failed/weak generated code is re-sent
    to Copilot; SAVED testcases are never touched.
    """
    from web.batch_target_resolution import ordered_preview_rows, sort_candidate_ids_by_preview_order

    drafts = gtest_state.get("drafts") or {}
    retry_ids = [
        cid
        for cid, d in drafts.items()
        if isinstance(d, dict)
        and str(d.get("code_status") or "").upper() in {"NEEDS_REVIEW", "ERROR"}
    ]
    if not retry_ids:
        return []
    ordered = ordered_preview_rows(bundle, language=language)
    return sort_candidate_ids_by_preview_order(retry_ids, ordered)


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
        exemplar_code_chars = 1200 if slim_prompt else 9000
        exemplar_io_chars = 500 if slim_prompt else 2500
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
        folder_block = "Project code files (context): " + ", ".join(folder_files[: (6 if slim_prompt else 20)]) + "\n\n"

    targets_block: list[str] = []
    target_chars = 800 if slim_prompt else 2800
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
    instruction_chars = 1200 if slim_prompt else 12_000
    instruction_block = (
        "Project instruction (primary — follow exactly):\n"
        f"{_clip(instruction, instruction_chars)}\n\n"
        if instruction
        else ""
    )
    stored_instruction_block = "" if instruction_block else str(context.get("project_instruction") or "")

    scope_bits = [
        "Generate ONLY the testcase IDs listed in this API chunk. "
        "Preserve their import order exactly. Do not add, regroup, or rename testcase IDs.",
    ]
    if scope_label:
        scope_bits.append(f"Selection: {scope_label}.")
    if import_group_label:
        scope_bits.append(f"Import Test Group: {import_group_label}.")
    scope_bits.append(
        "Sample .cc and saved examples are style references only — do not generate extra testcase IDs from them."
    )
    grouping_block = " ".join(scope_bits) + "\n\n"

    # Build the primary style example block.
    # slim_prompt: 600 chars (captures a full Japanese TEST_F ≈570 chars without truncation).
    # full prompt: 3000 chars.
    # Only embed as required when the snippet is genuinely representative (score > 1).
    # Generic/low-quality samples go in optional_parts instead.
    _style_chars = 600 if slim_prompt else 3000
    raw_style_snippet = str(context.get("style_example_snippet") or "").strip()
    _style_score = _style_example_score(raw_style_snippet)
    _style_is_required = _style_score > 1  # must have at least one project-specific feature
    style_snippet = _clip(raw_style_snippet, _style_chars) if raw_style_snippet else ""
    style_label = str(context.get("style_example_label") or "")
    style_example_block = build_style_example_block(style_snippet, label=style_label) if (style_snippet and _style_is_required) else ""
    style_example_optional = build_style_example_block(style_snippet, label=style_label) if (style_snippet and not _style_is_required) else ""

    memory_block = str(context.get("testcode_memory") or "")
    memory_note = (
        "Use Project Test Code Memory below as the primary style/fixture/API reference.\n\n"
        if memory_block else ""
    )
    no_sample_note = (
        ""  # style example covers it when present
        if style_example_block else
        "No sample .cc is provided — use TODO_REVIEW_Fixture and TODO_REVIEW patterns for unknown API/fixture names.\n\n"
        if not samples_text else ""
    )

    required_head = (
        "You are Microsoft 365 Copilot generating Google Test C++ for automotive software.\n\n"
        "Primary goal: Generate one editable GTest .cc draft per testcase_id.\n\n"
        f"{grouping_block}"
        "Generation rules:\n"
        "1. Generate as much concrete GTest code as possible from the testcase Given/When/Then.\n"
        "2. Preserve testcase_id exactly in the TEST_F name and in a comment.\n"
        "3. Follow the STYLE EXAMPLE structure exactly when one is provided.\n"
        "4. If fixture class is unknown, use TODO_REVIEW_Fixture as the fixture name.\n"
        "5. If an input signal API is unknown, write: // TODO_REVIEW: set input <signal_name>\n"
        "6. If output assertion API is unknown, write: // TODO_REVIEW: assert <signal_name> == <value>\n"
        "7. Do not return [TESTCASE_CODE] none when testcase has a meaningful Given, When, or Then.\n"
        "8. Return UNRESOLVED only when testcase intent is truly empty or impossible to understand.\n"
        "9. Missing API names is NOT a reason to return UNRESOLVED — use TODO_REVIEW instead.\n"
        "10. Map Given/When from expected_input; map Then from expected_output.\n\n"
        f"{memory_note}"
        f"{memory_block}"
        f"{style_example_block}"
        f"{no_sample_note}"
        f"{context.get('spec_context') or ''}"
        f"{folder_block}"
    )
    # Instruction and low-quality style examples are optional (trimmed when budget is tight)
    optional_parts = [
        ("Project instruction:\n", instruction_block or stored_instruction_block),
        ("Optional internal hints:\n", str(context.get("config_hints") or "")),
        ("Sample .cc style reference:\n", style_example_optional),  # generic sample if not required
        ("Additional sample .cc snippets:\n", f"Additional sample .cc snippets:\n{samples_text}\n" if samples_text and not style_example_block and not style_example_optional else ""),
        ("Saved code examples (style only):\n", saved_text),
        ("Accepted exemplar:\n", exemplar_block if not style_example_block else ""),
        ("Additional project GTest snippets:\n", ref_block),
    ]
    tail = (
        f"Testcase rows for this API chunk ({len(target_rows)}):\n"
        + "\n---\n".join(targets_block)
        + "\n\nRequired output format (one block per testcase_id):\n"
        "[TESTCASE_CODE]\n"
        "testcase_id: TC_xxx\n"
        "```cpp\n"
        "// TC: TC_xxx\n"
        "// TODO_REVIEW: update fixture/API names to match project\n"
        "TEST_F(TODO_REVIEW_Fixture, TC_xxx) {\n"
        "    // Given\n"
        "    // TODO_REVIEW: setup input signals from testcase Given section\n\n"
        "    // When\n"
        "    // TODO_REVIEW: trigger behavior from testcase When section\n\n"
        "    // Then\n"
        "    // TODO_REVIEW: assert expected outputs from testcase Then section\n"
        "}\n"
        "```\n"
        "(generate real code at every location where testcase data is available; "
        "use TODO_REVIEW only where project-specific details are unknown)\n\n"
        "[UNRESOLVED]\n"
        "Only list testcase IDs where testcase intent is too empty to generate any useful draft.\n"
        "testcase_id: <id>\n"
        "reason: <short reason>\n"
        "(or write \"none\")\n\n"
        "[ASSUMPTIONS]\n"
        "- Short bullet list only (max 5 lines)\n\n"
        "Before answering, verify:\n"
        "1. Did I generate one code block per testcase_id that has meaningful Given/When/Then?\n"
        "2. Did I avoid [TESTCASE_CODE] none for testcases with usable content?\n"
        "3. Did I use TODO_REVIEW instead of UNRESOLVED for missing API/fixture/signal details?\n"
        "4. Did I preserve every testcase_id exactly?\n"
    )
    return _budget_join(
        required_parts=[required_head],
        optional_parts=optional_parts,
        tail_parts=[tail],
        budget=budget,
    )


def build_copilot_minimal_prompt(target_rows: list[dict[str, Any]], *, engineer_note: str = "") -> str:
    """Fast retry prompt (used after timeout). Always requests best-effort draft code."""
    blocks: list[str] = []
    for row in target_rows:
        cid = str(row.get("candidate_id") or "")
        event = str(row.get("event") or row.get("test_function") or "").strip()
        blocks.append(
            f"testcase_id: {cid}\n"
            f"event: {event}\n"
            f"expected_input:\n{_clip(row.get('expected_input'), 650)}\n"
            f"expected_output:\n{_clip(row.get('expected_output'), 650)}"
        )
    return _clip(
        "Generate Google Test C++ .cc code for ALEX (fast mode).\n\n"
        "Goal: one editable GTest draft per testcase_id.\n"
        "Rules:\n"
        "- Use TODO_REVIEW_Fixture if fixture is unknown.\n"
        "- Use TODO_REVIEW comments for unknown API/signal/assertion/timing.\n"
        "- Do not return [TESTCASE_CODE] none when testcase has Given/When/Then content.\n"
        "- UNRESOLVED only when testcase intent is truly empty.\n"
        "- Preserve testcase_id exactly.\n\n"
        "Output format:\n"
        "[TESTCASE_CODE]\n"
        "testcase_id: <id>\n"
        "```cpp\n"
        "TEST_F(TODO_REVIEW_Fixture, <id>) {\n"
        "    // Given: ...\n"
        "    // When: ...\n"
        "    // Then: ...\n"
        "}\n"
        "```\n"
        "[UNRESOLVED]\nnone\n"
        "[ASSUMPTIONS]\n- max 3 bullets\n\n"
        + (f"Project instruction:\n{_clip(engineer_note, 700)}\n\n" if engineer_note else "")
        + "Testcase rows:\n"
        + "\n---\n".join(blocks),
        3500,
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
    allow_missing_sample: bool = True,
    slim_prompt: bool = True,
    prompt_budget: int | None = None,
) -> dict[str, Any]:
    context = collect_copilot_project_context(bundle, gtest_state, language=language, slim_prompt=slim_prompt)
    missing_sample = (
        not context.get("sample_blocks")
        and not context.get("saved_examples")
        and not context.get("exemplar")
    )
    if missing_sample and not allow_missing_sample:
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
                "_target_rows": rows,
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
        "missing_sample_warning": "No sample .cc loaded — generating from testcase rows only. Load sample .cc to improve output quality." if missing_sample else "",
        "context_summary": {
            "samples": len(context.get("sample_blocks") or []),
            "saved_examples": len(context.get("saved_examples") or []),
            "has_exemplar": bool(context.get("exemplar")),
            "reference_snippets": len(context.get("reference_snippets") or []),
            "slim_prompt": bool(slim_prompt),
            "missing_sample": missing_sample,
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
    persist_errors: bool = True,
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
            # UNRESOLVED from Copilot → NEEDS_REVIEW with scaffold, never ERROR.
            # Reason: Copilot marks UNRESOLVED when API/fixture/sample is missing —
            # that is not an ALEX error; user can edit the scaffold.
            unresolved_reason = str(unresolved_by_id[cid] or "Copilot returned UNRESOLVED for this testcase.")
            row = next((r for r in (expected_candidate_ids or []) if r == cid), None)
            row_data = next((r for r in (gtest_state.get("_batch_target_rows") or []) if str(r.get("candidate_id") or "") == cid), {"candidate_id": cid})
            scaffold = _persist_review_scaffold(
                gtest_state,
                row=row_data,
                reason=f"Copilot UNRESOLVED: {unresolved_reason}",
                generation_source=generation_source,
            )
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "NEEDS_REVIEW",
                    "workflow_message": f"Copilot UNRESOLVED: {unresolved_reason}",
                    "code_status": "NEEDS_REVIEW",
                    "full_snippet": scaffold,
                    "issue_reason": "unresolved_by_copilot",
                }
            )
            needs_review += 1
            continue

        if cid not in parsed_by_id:
            # testcase_id not found in response: true parse error → ERROR
            msg = "testcase_id not found in Copilot API chunk output"
            if persist_errors:
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
            # No usable TEST_F block → ERROR
            msg = "parse failed — no TEST_F in block"
            if persist_errors:
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
    clarification_note: str = "",
    batch_size: int | None = None,
    skip_saved: bool = False,
    scope: str = "filter",
    group_key: str = "",
    group_field: str = "test_group",
    exclude_candidate_ids: list[str] | None = None,
    progress_callback: Any | None = None,
    cancel_check: Any | None = None,
    retry_count: int = 0,
    allow_missing_sample: bool = True,
    user_id: str | None = None,
    slim_prompt: bool = True,
    prompt_budget: int | None = None,
) -> dict[str, Any]:
    if clarification_note:
        note_prefix = f"Additional clarification for this retry:\n{clarification_note.strip()}\n\n"
        engineer_note = note_prefix + str(engineer_note or "")
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
    total_fallback = 0
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
        prompt_for_api = str(batch.get("prompt") or "")
        prompt_for_web_fallback = prompt_for_api
        chat = run_copilot_chat_result(
            cfg,
            prompt_for_api,
            reuse_session_conversation=(idx > 0 and not slim_prompt),
            user_id=user_id,
        )
        if not chat.get("ok") and str(chat.get("error_category") or "") == "m365_graph_timeout":
            rows_for_retry = list(batch.get("_target_rows") or [])
            prompt_for_api = build_copilot_minimal_prompt(rows_for_retry, engineer_note=engineer_note)
            run["status_message"] = f"Copilot API chunk {idx + 1}/{len(prompts)} timed out; retrying fast minimal prompt."
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
                    completed_chunks=run.get("completed_chunks", idx),
                    failed_chunks=run.get("failed_chunks", 0),
                    failed_chunk_details=run.get("failed_chunk_details", []),
                    retry_count=int(run.get("retry_count", 0)) + 1,
                    status_message=run["status_message"],
                )
            chat = run_copilot_chat_result(
                cfg,
                prompt_for_api,
                reuse_session_conversation=False,
                user_id=user_id,
                persist_conversation=False,
            )
        run["last_response_s"] = round(perf_counter() - response_started, 1)
        if not chat.get("ok"):
            msg = str(chat.get("error") or "M365 API failed")
            category = str(chat.get("error_category") or "m365_copilot_api")
            failed_ids = list(batch.get("candidate_ids") or [])
            fallback_mode = category == "m365_graph_timeout"
            detail = {
                "batch_index": idx + 1,
                "candidate_ids": failed_ids,
                "reason": msg,
                "error_category": category,
                "last_response_s": run.get("last_response_s"),
                "fallback_prompt": prompt_for_web_fallback,
            }
            details = list(run.get("failed_chunk_details") or [])
            details.append(detail)
            run["failed_chunk_details"] = details
            run["failed_chunks"] = len(details)
            run["failed_candidate_ids"] = list(dict.fromkeys([*list(run.get("failed_candidate_ids") or []), *failed_ids]))
            run["failed_chunk_reason"] = msg
            run["failed_chunk_error_category"] = category
            run["fallback_prompt"] = prompt_for_web_fallback
            run["completed_chunks"] = idx + 1
            run["status_message"] = f"Copilot API chunk {idx + 1}/{len(prompts)} failed: {msg}"
            for cid in batch.get("candidate_ids") or []:
                row = next((r for r in list(batch.get("_target_rows") or []) if str(r.get("candidate_id") or "") == str(cid)), {})
                if not fallback_mode:
                    persist_batch_generation_error(
                        gtest_state, candidate_id=cid, error_message=msg, generation_source="COPILOT_BATCH"
                    )
                scaffold = _persist_review_scaffold(
                    gtest_state,
                    row=row or {"candidate_id": cid},
                    reason=msg,
                ) if fallback_mode else ""
                all_results.append(
                    {
                        "candidate_id": cid,
                        "ok": False,
                        "workflow_status": "NEEDS_REVIEW" if fallback_mode else "ERROR",
                        "workflow_message": msg,
                        "code_status": "NEEDS_REVIEW" if fallback_mode else "ERROR",
                        "full_snippet": scaffold,
                        "fallback_prompt": prompt_for_web_fallback,
                    }
                )
                if fallback_mode:
                    total_review += 1
                    total_fallback += 1
                else:
                    total_error += 1
            run["saved"] = total_saved
            run["needs_review"] = total_review
            run["error"] = total_error
            run["fallback"] = total_fallback
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
            if job_output:
                from pathlib import Path as _Path
                flush_batch_run_checkpoint(_Path(job_output), gtest_state)
            continue

        raw = str(chat.get("reply") or chat.get("content") or chat.get("text") or "")
        # Stash target rows so UNRESOLVED scaffold can reference them
        gtest_state["_batch_target_rows"] = list(batch.get("_target_rows") or [])
        one = apply_copilot_batch_import(
            bundle,
            gtest_state,
            job_output,
            content=raw,
            expected_candidate_ids=batch.get("candidate_ids"),
            language=language,
            generation_source="COPILOT_BATCH",
            persist_errors=False,
        )
        gtest_state.pop("_batch_target_rows", None)
        chunk_results = list(one.get("results") or [])
        s = dict(one.get("summary") or {})
        run = gtest_state.setdefault("copilot_batch", {}).setdefault("run", {})
        chunk_error_results = [
            r for r in chunk_results
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
                "fallback_prompt": prompt_for_web_fallback,
            }
            details = list(run.get("failed_chunk_details") or [])
            details.append(detail)
            run["failed_chunk_details"] = details
            run["failed_chunks"] = len(details)
            run["failed_candidate_ids"] = list(dict.fromkeys([*list(run.get("failed_candidate_ids") or []), *failed_ids]))
            run["failed_chunk_reason"] = reason
            run["fallback_prompt"] = prompt_for_web_fallback
            if not int(s.get("saved") or 0) and not int(s.get("needs_review") or 0):
                converted = 0
                for r in chunk_results:
                    if str(r.get("workflow_status") or r.get("code_status") or "").upper() == "ERROR":
                        cid = str(r.get("candidate_id") or "")
                        row = next(
                            (rr for rr in list(batch.get("_target_rows") or []) if str(rr.get("candidate_id") or "") == cid),
                            {"candidate_id": cid},
                        )
                        scaffold = _persist_review_scaffold(
                            gtest_state,
                            row=row,
                            reason=str(r.get("workflow_message") or reason),
                        )
                        r["workflow_status"] = "NEEDS_REVIEW"
                        r["code_status"] = "NEEDS_REVIEW"
                        r["full_snippet"] = scaffold
                        r["fallback_prompt"] = prompt_for_web_fallback
                        converted += 1
                s["needs_review"] = converted
                s["fallback"] = converted
                s["error"] = 0
        for r in chunk_results:
            all_results.append(r)
        total_saved += int(s.get("saved") or 0)
        total_review += int(s.get("needs_review") or 0)
        total_error += int(s.get("error") or 0)
        total_fallback += int(s.get("fallback") or 0)
        run.update(
            {
                "saved": total_saved,
                "needs_review": total_review,
                "error": total_error,
                "fallback": total_fallback,
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
        if job_output:
            from pathlib import Path as _Path
            flush_batch_run_checkpoint(_Path(job_output), gtest_state)

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
        "fallback": total_fallback,
        "skipped": 0,
        "total": built.get("target_count") or len(all_results),
    }
    ok = total_saved > 0 or total_review > 0 or total_fallback > 0
    failure_reason = ""
    failure_category = ""
    if not ok:
        details = run.get("failed_chunk_details") or []
        if details:
            failure_reason = str(details[-1].get("reason") or "")
            failure_category = str(details[-1].get("error_category") or "")
        failure_reason = failure_reason or str(run.get("failed_chunk_reason") or "")
        failure_category = failure_category or str(run.get("failed_chunk_error_category") or "")
        if not failure_reason and all_results:
            failure_reason = str(
                all_results[0].get("workflow_message")
                or all_results[0].get("error")
                or ""
            )
        failure_reason = failure_reason or "Copilot response did not contain usable [TESTCASE_CODE] or [UNRESOLVED] output."
    if job_output:
        from pathlib import Path as _Path
        flush_batch_run_checkpoint(_Path(job_output), gtest_state)
    return {
        "ok": ok,
        "error": failure_reason if not ok else "",
        "error_category": failure_category or ("m365_copilot_batch" if not ok else ""),
        "fallback_required": bool(total_fallback),
        "fallback_prompt": str(run.get("fallback_prompt") or ""),
        "batch_count": len(prompts),
        "batch_size": built.get("batch_size"),
        "results": all_results,
        "summary": summary,
        "context_summary": built.get("context_summary"),
    }
