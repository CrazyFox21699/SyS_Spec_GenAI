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

_BATCH_MAX_PROMPT_CHARS = 20_000   # reduced: shorter prompts → fewer timeouts
_BATCH_TARGET_CHARS = 1_200
_DEFAULT_BATCH_SIZE = 1
_ALLOWED_BATCH_SIZES = (1, 3, 5, 10, 20)   # 3 added as safe middle option
_SLIM_PROMPT_BUDGET = 4_000        # reduced: keep prompts tight
_FULL_PROMPT_BUDGET = 15_000       # reduced: avoid graph timeout on large prompts

_TESTCASE_CODE_SECTION_RE = re.compile(
    r"\[TESTCASE_CODE\](.*?)(?=\[ASSUMPTIONS\]|\[UNRESOLVED\]|\[MISSING_CONTEXT\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_ASSUMPTIONS_SECTION_RE = re.compile(
    r"\[ASSUMPTIONS\](.*?)(?=\[UNRESOLVED\]|\[MISSING_CONTEXT\]|$)",
    re.IGNORECASE | re.DOTALL,
)
_UNRESOLVED_SECTION_RE = re.compile(r"\[UNRESOLVED\](.*)$", re.IGNORECASE | re.DOTALL)
_MISSING_CONTEXT_SECTION_RE = re.compile(
    r"\[MISSING_CONTEXT\](.*?)(?=\[TESTCASE_CODE\]|\[UNRESOLVED\]|\[ASSUMPTIONS\]|$)",
    re.IGNORECASE | re.DOTALL,
)
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


def _sanitize_reason(reason: str, max_len: int = 200) -> str:
    """Strip JSON/API error bodies from a reason string for display in code comments."""
    text = str(reason or "Copilot API did not return concrete code.")
    # Remove anything that looks like JSON (starts with { or [)
    text = re.sub(r"\{[^}]{20,}\}", "[API error detail hidden]", text, flags=re.DOTALL)
    text = re.sub(r"\[[^\]]{20,}\]", "[API detail hidden]", text, flags=re.DOTALL)
    # Remove HTTP headers / long lines
    text = re.sub(r"HTTPSConnectionPool\([^)]*\)[^.]*\.", "Copilot API timeout.", text)
    text = text.replace('"', "'")
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."
    return text


def _review_scaffold_code(row: dict[str, Any], reason: str) -> str:
    cid = str(row.get("candidate_id") or row.get("id") or "").strip()
    event = str(row.get("event") or row.get("test_function") or "").strip()
    test_name = _cpp_ident(cid or event, "GeneratedTestcase")
    # Short display reason only — full error stored in draft metadata
    reason_display = _sanitize_reason(reason)
    return (
        f"// {cid} {event}".rstrip() + "\n"
        "// NEEDS_REVIEW: Copilot API fallback scaffold. Retry generation or edit manually.\n"
        f"// Reason: {reason_display}\n"
        f"TEST(AlexGeneratedFallback, {test_name}) {{\n"
        f"  GTEST_SKIP() << \"NEEDS_REVIEW: Copilot API failed. Retry generation.\";\n"
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
            "fallback_reason": _sanitize_reason(reason),
            "fallback_error_detail": str(reason or "")[:2000],  # full error stored here, not in code
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
    from web.project_testcode_memory import memory_for_prompt_prioritized

    cache = gtest_state.get("project_code_config_cache") or {}
    mem = str(cache.get("project_testcode_memory.md") or "").strip()
    if not mem:
        return ""
    limit = 3000 if slim_prompt else 5000
    # Use prioritized version: quick_add rules + high-value sections first
    clipped = memory_for_prompt_prioritized(mem, char_limit=limit)
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


def analyze_missing_generation_context(
    row: dict[str, Any],
    gtest_state: dict[str, Any],
) -> list[dict[str, str]]:
    """Detect what project context is missing for generating code for this testcase.

    Returns a list of missing-item dicts so the user can add rules via Quick Add
    before or after generation. Does NOT block generation.
    """
    items: list[dict[str, str]] = []
    cid = str(row.get("candidate_id") or "")
    expected_input = str(row.get("expected_input") or "")
    expected_output = str(row.get("expected_output") or "")
    cache = gtest_state.get("project_code_config_cache") or {}
    memory = str(cache.get("project_testcode_memory.md") or "")
    memory_upper = memory.upper()

    # No intent at all
    if not expected_input.strip() and not expected_output.strip():
        items.append({
            "type": "missing_testcase_intent",
            "signal": "",
            "description": "No Given/When/Then content in testcase",
            "suggested_action": "Edit testcase row to add expected input/output",
            "rule_type": "",
        })
        return items

    # Fixture
    has_fixture = bool(re.search(r"\bTEST_F\b", memory)) or bool(re.search(r"Fixture", memory, re.I))
    if not has_fixture:
        items.append({
            "type": "missing_fixture",
            "signal": "",
            "description": "No fixture class defined in Project Test Code Memory",
            "suggested_action": "Add Fixture / Test Style Rule",
            "rule_type": "fixture_style",
        })

    # Input signals from Given: SIGNAL=value
    for sig in dict.fromkeys(re.findall(r"Given:\s*(\w+)\s*=", expected_input, re.I)):
        if sig.upper() not in memory_upper and "RTE_READ_" + sig.upper() not in memory_upper:
            items.append({
                "type": "missing_input_mock_api",
                "signal": sig,
                "description": f"No input mock / RTE API mapping for signal {sig}",
                "suggested_action": f"Add Input/Mock Rule for {sig}",
                "rule_type": "input_mock",
            })

    # Output signals from Then: SIGNAL=value
    for sig in dict.fromkeys(re.findall(r"Then:\s*(\w+)\s*=", expected_output, re.I)):
        if sig.upper() not in memory_upper:
            items.append({
                "type": "missing_output_assertion",
                "signal": sig,
                "description": f"No output assertion variable/API for {sig}",
                "suggested_action": f"Add Output/Assertion Rule for {sig}",
                "rule_type": "output_assertion",
            })

    # Timing
    has_timing_spec = bool(re.search(r"(?:elapsed|T\s*=\s*\d+|wait|cycle|ms|step)", expected_input, re.I))
    has_timing_memory = bool(re.search(r"igsw_Main_Run|RunForMs|WaitMs|Timing Pattern", memory, re.I))
    if has_timing_spec and not has_timing_memory:
        items.append({
            "type": "missing_timing_pattern",
            "signal": "",
            "description": "Timing/cycle pattern referenced in testcase but not in memory",
            "suggested_action": "Add Timing Rule (e.g. igsw_Main_Run cycle pattern)",
            "rule_type": "timing",
        })

    return items


def _format_missing_context_for_prompt(missing_items: list[dict[str, str]]) -> str:
    """Format missing context list as a compact prompt hint."""
    if not missing_items:
        return ""
    lines = ["MISSING CONTEXT (place TODO_REVIEW at these exact locations):"]
    for item in missing_items:
        sig = item.get("signal") or ""
        sig_str = f" for `{sig}`" if sig else ""
        lines.append(f"- {item.get('type','').replace('_',' ')}{sig_str}: {item.get('description','')}")
    return "\n".join(lines) + "\n\n"


def _extract_generation_critical_map(memory_content: str, *, char_limit: int = 800) -> str:
    """Extract the highest-value sections from memory for concrete code generation.

    Returns a compact string with fixture/API/assertion/timing rules only.
    This replaces dumping the full memory into prompts.
    """
    from web.project_testcode_memory import _section_body

    text = str(memory_content or "").strip()
    if not text:
        return ""

    # Sections in priority order — most actionable for generating code first
    priority_sections = [
        "Spec Signal to Test Code Map",
        "Fixture / Observable Variables",
        "RTE API Map",
        "Input Mock Pattern",
        "Output Assertion Pattern",
        "Timing Pattern",
        "Default Mock Behavior",
        "Fixture / Test Style",
        "Constants / Value Map",
        "Reviewer Notes / Learned Fixes",
    ]

    parts: list[str] = []
    for section in priority_sections:
        body = _section_body(text, section)
        if not body:
            continue
        bullets = [
            l.strip() for l in body.splitlines()
            if l.strip().startswith("-") and l.strip() != "-"
        ][:4]  # max 4 bullets per section
        if bullets:
            parts.append(f"{section}:\n" + "\n".join(bullets))

    result = "\n".join(parts)
    if not result:
        return ""
    if len(result) <= char_limit:
        return result
    return result[:char_limit].rstrip() + "\n...[trimmed]"


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
        # Compact critical map extracted from memory — higher value than full memory dump
        "critical_map": _extract_generation_critical_map(
            str((gtest_state.get("project_code_config_cache") or {}).get("project_testcode_memory.md") or ""),
            char_limit=600 if slim_prompt else 1200,
        ),
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

    # --- Target rows + missing context report per TC ---
    target_chars = 700 if slim_prompt else 2000
    targets_block: list[str] = []
    # Build a minimal gtest_state-like dict from context so we can analyze missing context
    _ctx_cache = {"project_testcode_memory.md": str(context.get("testcode_memory") or "")}
    _ctx_gstate = {"project_code_config_cache": _ctx_cache}
    for row in target_rows:
        cid = str(row.get("candidate_id") or "")
        event = str(row.get("event") or row.get("test_function") or "").strip()
        # Analyze missing context and attach to row prompt
        missing = analyze_missing_generation_context(row, _ctx_gstate)
        missing_hint = _format_missing_context_for_prompt(missing) if missing else ""
        targets_block.append(
            f"testcase_id: {cid}\n"
            + (f"event: {event}\n" if event else "")
            + f"Given/When (expected_input):\n{_clip(row.get('expected_input'), target_chars)}\n"
            + f"Then (expected_output):\n{_clip(row.get('expected_output'), target_chars)}\n"
            + (missing_hint if missing_hint else "")
        )

    # --- Style example (compact, high-score only as required) ---
    _style_chars = 600 if slim_prompt else 2000
    raw_style_snippet = str(context.get("style_example_snippet") or "").strip()
    _style_score = _style_example_score(raw_style_snippet)
    _style_is_required = _style_score > 1
    style_snippet = _clip(raw_style_snippet, _style_chars) if raw_style_snippet else ""
    style_label = str(context.get("style_example_label") or "")
    style_example_block = build_style_example_block(style_snippet, label=style_label) if (style_snippet and _style_is_required) else ""
    style_example_optional = build_style_example_block(style_snippet, label=style_label) if (style_snippet and not _style_is_required) else ""

    # --- Generation Critical Map (compact, most actionable memory) ---
    critical_map = str(context.get("critical_map") or "").strip()
    critical_map_block = (
        "GENERATION CRITICAL MAP (use this when writing code):\n"
        f"{critical_map}\n\n"
        if critical_map else ""
    )

    # --- Chunk scope ---
    scope_bits = [f"Generate ONLY these {len(target_rows)} testcase(s):"]
    if scope_label:
        scope_bits.append(f"[{scope_label}]")
    if import_group_label:
        scope_bits.append(f"Group: {import_group_label}")
    chunk_header = " ".join(scope_bits) + "\n\n"

    # --- Compact rules (no TODO_REVIEW encouragement) ---
    rules = (
        "RULES:\n"
        "1. Use fixture/API/assertion from GENERATION CRITICAL MAP if available.\n"
        "2. Follow the STYLE EXAMPLE structure exactly.\n"
        "3. Do NOT invent API names. Do NOT fill unknown APIs with TODO_REVIEW placeholders.\n"
        "4. If required API/mapping is missing, return MISSING_CONTEXT for that testcase.\n"
        "5. Generate real code only when fixture, input API, and output variable are known.\n"
        "6. UNRESOLVED only if testcase has zero Given/When/Then content.\n\n"
    )

    # --- Engineer instruction (short) ---
    instruction = str(engineer_note or "").strip()
    instruction_block = (
        f"Instruction: {_clip(instruction, 600 if slim_prompt else 3000)}\n\n"
        if instruction else ""
    )
    stored_instruction_block = "" if instruction_block else _clip(str(context.get("project_instruction") or ""), 400)
    stored_instruction_block = f"Instruction: {stored_instruction_block}\n\n" if stored_instruction_block else ""

    required_head = (
        "TASK: Generate one GTest TEST_F per testcase_id below.\n\n"
        f"{chunk_header}"
        f"{rules}"
        f"{critical_map_block}"
        f"{style_example_block}"
    )

    # Optional: instruction, fallback style for low-score samples, saved examples
    optional_parts = [
        ("Instruction:\n", instruction_block or stored_instruction_block),
        ("Sample style:\n", style_example_optional),
        ("Saved example:\n", saved_text[:1] if saved_text else ""),  # 1 saved example max
        ("Exemplar:\n", exemplar_block if not style_example_block else ""),
    ]

    tail = (
        f"TESTCASES ({len(target_rows)}):\n"
        + "\n---\n".join(targets_block)
        + "\n\nOUTPUT FORMAT (use exactly one section per testcase):\n"
        "[TESTCASE_CODE]\n"
        "testcase_id: <id>\n"
        "```cpp\n<real project-style TEST_F code — no TODO_REVIEW placeholders>\n```\n\n"
        "[MISSING_CONTEXT]\n"
        "testcase_id: <id>\n"
        "missing_type: INPUT_API | OUTPUT_ASSERTION | FIXTURE | TIMING | CONSTANT\n"
        "signal_or_item: <signal or variable name>\n"
        "reason: <brief reason>\n"
        "suggested_rule_type: Input / Mock Rule | Output / Assertion Rule | Fixture Rule | Timing Rule\n"
        "(use [MISSING_CONTEXT] when required API/mapping is not in memory — do NOT write fake code)\n\n"
        "[UNRESOLVED]\nnone (only for testcases with no Given/When/Then at all)\n\n"
        "[ASSUMPTIONS]\n<max 3 bullets>\n"
    )
    return _budget_join(
        required_parts=[required_head],
        optional_parts=optional_parts,
        tail_parts=[tail],
        budget=budget,
    )


def build_copilot_minimal_prompt(
    target_rows: list[dict[str, Any]],
    *,
    engineer_note: str = "",
    critical_map: str = "",
) -> str:
    """Compact retry prompt (used after timeout). Includes critical map for concrete code."""
    blocks: list[str] = []
    for row in target_rows:
        cid = str(row.get("candidate_id") or "")
        event = str(row.get("event") or row.get("test_function") or "").strip()
        blocks.append(
            f"testcase_id: {cid}\n"
            + (f"event: {event}\n" if event else "")
            + f"Given/When:\n{_clip(row.get('expected_input'), 500)}\n"
            + f"Then:\n{_clip(row.get('expected_output'), 500)}"
        )
    critical_section = f"CRITICAL MAP:\n{_clip(critical_map, 500)}\n\n" if critical_map else ""
    return _clip(
        f"TASK: Generate real project-style TEST_F per testcase (fast retry, {len(target_rows)} TC).\n"
        "RULES: Use fixture/API from CRITICAL MAP. Do NOT invent API names. "
        "If API/mapping unknown, return MISSING_CONTEXT. No UNRESOLVED unless content is empty.\n\n"
        f"{critical_section}"
        + (f"Instruction: {_clip(engineer_note, 400)}\n\n" if engineer_note else "")
        + "TESTCASES:\n"
        + "\n---\n".join(blocks)
        + "\n\nOUTPUT:\n"
        "[TESTCASE_CODE]\ntestcase_id: <id>\n```cpp\n<real TEST_F code>\n```\n"
        "[MISSING_CONTEXT]\ntestcase_id: <id>\nmissing_type: INPUT_API|OUTPUT_ASSERTION|FIXTURE|TIMING\n"
        "signal_or_item: <name>\nreason: <brief>\nsuggested_rule_type: <rule type>\n"
        "[UNRESOLVED]\nnone\n",
        3000,
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


def _parse_missing_context_blocks(raw: str) -> dict[str, list[dict[str, str]]]:
    """Parse all [MISSING_CONTEXT] blocks from a Copilot response.

    Returns: {testcase_id: [list of missing item dicts]}
    Each item has: missing_type, signal_or_item, reason, suggested_rule_type.
    """
    result: dict[str, list[dict[str, str]]] = {}
    # Find all [MISSING_CONTEXT] blocks, each may cover one testcase_id
    for block_m in _MISSING_CONTEXT_SECTION_RE.finditer(raw):
        block = block_m.group(1).strip()
        if not block:
            continue
        # A single block may contain multiple entries separated by blank lines or repeated testcase_id
        # Parse key:value lines
        current_id = ""
        current_item: dict[str, str] = {}
        for line in block.splitlines():
            line = line.strip()
            if not line:
                if current_id and current_item:
                    result.setdefault(current_id, []).append(current_item)
                    current_item = {}
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower().replace(" ", "_").replace("-", "_")
                val = val.strip()
                if key == "testcase_id":
                    if current_id and current_item:
                        result.setdefault(current_id, []).append(current_item)
                        current_item = {}
                    current_id = val
                elif key in ("missing_type", "signal_or_item", "reason", "suggested_rule_type"):
                    current_item[key] = val
        if current_id and current_item:
            result.setdefault(current_id, []).append(current_item)
    return result


def parse_copilot_batch_response(text: str) -> dict[str, Any]:
    """Parse [TESTCASE_CODE] / [MISSING_CONTEXT] / [UNRESOLVED] / [ASSUMPTIONS] batch output."""
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

    # Parse [MISSING_CONTEXT] blocks — Copilot signals missing API/fixture info
    missing_context_by_id = _parse_missing_context_blocks(raw)

    unresolved_list = [f"{k}: {v}" for k, v in unresolved_by_id.items()]
    return {
        "ok": bool(items) or bool(unresolved_by_id) or bool(missing_context_by_id),
        "items": items,
        "assumptions": assumptions,
        "unresolved": unresolved_list,
        "unresolved_by_id": unresolved_by_id,
        "missing_context_by_id": missing_context_by_id,
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
    missing_context_by_id = dict(parsed.get("missing_context_by_id") or {})
    parsed_by_id = {str(i["candidate_id"]): i for i in parsed.get("items") or [] if i.get("candidate_id")}

    if not parsed_by_id and not unresolved_by_id and not missing_context_by_id:
        return {
            "ok": False,
            "error": parsed.get("error") or "No [TESTCASE_CODE], [MISSING_CONTEXT], or [UNRESOLVED] blocks parsed.",
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
    target_ids = list(expected) if expected else list(
        set(parsed_by_id) | set(unresolved_by_id) | set(missing_context_by_id)
    )

    results: list[dict[str, Any]] = []
    saved = needs_review = error = skipped = 0

    for cid in target_ids:
        if cid in missing_context_by_id:
            # [MISSING_CONTEXT] from Copilot → NEEDS_REVIEW with structured missing info.
            # No GTEST_SKIP, no fake TODO_REVIEW code.
            mc_items = missing_context_by_id[cid]
            mc_summary = "; ".join(
                f"{it.get('missing_type','?')}/{it.get('signal_or_item','?')}"
                for it in mc_items
            )[:200]
            msg = f"Copilot MISSING_CONTEXT: {mc_summary}"
            # Store missing items in the draft for the UI Missing Input Report
            save_draft(
                gtest_state, draft_key=cid,
                draft={
                    "full_snippet": "",
                    "code_body": "",
                    "code_status": "NEEDS_REVIEW",
                    "workflow_message": msg,
                    "is_fallback_scaffold": False,
                    "is_partial_code": False,
                    "issue_reason": "missing_generation_context",
                    "missing_context": mc_items,
                    "generation_source": generation_source,
                },
                engineer_edited=False, wrap_markers=False,
            )
            results.append({
                "candidate_id": cid,
                "ok": False,
                "workflow_status": "NEEDS_REVIEW",
                "workflow_message": msg,
                "code_status": "NEEDS_REVIEW",
                "issue_reason": "missing_generation_context",
                "missing_context": mc_items,
            })
            needs_review += 1
            continue

        if cid in unresolved_by_id:
            # UNRESOLVED from Copilot → NEEDS_REVIEW, never ERROR.
            unresolved_reason = str(unresolved_by_id[cid] or "Copilot returned UNRESOLVED for this testcase.")
            row_data = next((r for r in (gtest_state.get("_batch_target_rows") or []) if str(r.get("candidate_id") or "") == cid), {"candidate_id": cid})
            # Analyze what context is missing (helps user fix it)
            missing = analyze_missing_generation_context(row_data, gtest_state)
            scaffold = _persist_review_scaffold(
                gtest_state,
                row=row_data,
                reason=f"Copilot UNRESOLVED: {unresolved_reason}",
                generation_source=generation_source,
            )
            # Store missing context in draft for UI
            if missing:
                existing_draft = (gtest_state.get("drafts") or {}).get(cid) or {}
                if existing_draft:
                    existing_draft["missing_context"] = missing
                    existing_draft["issue_reason"] = "missing_generation_context"
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "NEEDS_REVIEW",
                    "workflow_message": f"Copilot UNRESOLVED: {unresolved_reason}",
                    "code_status": "NEEDS_REVIEW",
                    "full_snippet": scaffold,
                    "issue_reason": "unresolved_by_copilot",
                    "missing_context": missing,
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
        if not full:
            # Empty block → ERROR (no code at all)
            msg = "parse failed — empty code block"
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

        if not re.search(r"\bTEST(?:_F)?\s*\(", full):
            # Has content but no TEST_F — keep as NEEDS_REVIEW (not ERROR)
            # Copilot returned something; user can edit it
            msg = "no TEST_F in block — code needs review/edit"
            save_draft(
                gtest_state,
                draft_key=cid,
                draft={
                    "full_snippet": full,
                    "code_body": full,
                    "code_status": "NEEDS_REVIEW",
                    "workflow_message": msg,
                    "is_partial_code": True,
                    "issue_reason": "parse_error",
                    "generation_source": generation_source,
                },
                engineer_edited=False,
                wrap_markers=True,
            )
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "NEEDS_REVIEW",
                    "workflow_message": msg,
                    "code_status": "NEEDS_REVIEW",
                }
            )
            needs_review += 1
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
        "missing_context_count": len(missing_context_by_id),
        "assumptions": parsed.get("assumptions"),
    }
    gtest_state.setdefault("copilot_batch", {})["last_results"] = results

    summary = {
        "saved": saved,
        "needs_review": needs_review,
        "error": error,
        "skipped": skipped,
        "total": len(target_ids),
        "missing_context": len(missing_context_by_id),
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
            # If chunk has > 1 TC, split to single-TC minimal prompt (reduce timeout risk)
            # If already single-TC, use minimal prompt with critical map
            _critical_map = str(
                (gtest_state.get("project_code_config_cache") or {}).get("project_testcode_memory.md") or ""
            )
            _critical_map_compact = _extract_generation_critical_map(_critical_map, char_limit=400) if _critical_map else ""
            if len(rows_for_retry) > 1:
                # Retry one at a time instead of the full chunk
                run["status_message"] = f"Copilot API chunk {idx + 1}/{len(prompts)} timed out; splitting into {len(rows_for_retry)} single-TC retries."
                _split_results: list[dict[str, Any]] = []
                _split_saved = _split_review = _split_error = 0
                for _single_row in rows_for_retry:
                    _single_prompt = build_copilot_minimal_prompt([_single_row], engineer_note=engineer_note, critical_map=_critical_map_compact)
                    _single_chat = run_copilot_chat_result(
                        cfg, _single_prompt,
                        reuse_session_conversation=False,
                        user_id=user_id,
                        persist_conversation=False,
                    )
                    if _single_chat.get("ok"):
                        _single_raw = str(_single_chat.get("reply") or _single_chat.get("content") or "")
                        gtest_state["_batch_target_rows"] = [_single_row]
                        _one = apply_copilot_batch_import(
                            bundle, gtest_state, job_output,
                            content=_single_raw,
                            expected_candidate_ids=[str(_single_row.get("candidate_id") or "")],
                            language=language, generation_source="COPILOT_BATCH", persist_errors=False,
                        )
                        gtest_state.pop("_batch_target_rows", None)
                        _s = _one.get("summary") or {}
                        _split_saved += int(_s.get("saved") or 0)
                        _split_review += int(_s.get("needs_review") or 0)
                        _split_error += int(_s.get("error") or 0)
                        _split_results.extend(_one.get("results") or [])
                    else:
                        cid = str(_single_row.get("candidate_id") or "")
                        _split_results.append({"candidate_id": cid, "ok": False,
                                               "workflow_status": "NEEDS_REVIEW", "code_status": "NEEDS_REVIEW",
                                               "workflow_message": "Single-TC retry timed out"})
                        _split_review += 1
                total_saved += _split_saved
                total_review += _split_review
                total_error += _split_error
                for r in _split_results:
                    all_results.append(r)
                run.update({"saved": total_saved, "needs_review": total_review, "error": total_error,
                             "completed_chunks": idx + 1, "queued_chunks": max(len(prompts) - idx - 1, 0),
                             "status_message": f"Chunk {idx + 1} split into single-TC retries."})
                if job_output:
                    from pathlib import Path as _Path
                    flush_batch_run_checkpoint(_Path(job_output), gtest_state)
                continue
            prompt_for_api = build_copilot_minimal_prompt(rows_for_retry, engineer_note=engineer_note, critical_map=_critical_map_compact)
            run["status_message"] = f"Copilot API chunk {idx + 1}/{len(prompts)} timed out; retrying compact prompt."
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
            # GTEST_SKIP scaffold is last resort only — use NEEDS_REVIEW with short reason for timeouts
            is_timeout = category == "m365_graph_timeout"
            is_api_fail = not is_timeout  # network error, 429, etc.
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
                row_data = row or {"candidate_id": cid}
                # Analyze what context is missing for this TC
                missing = analyze_missing_generation_context(row_data, gtest_state)
                has_missing_ctx = bool(missing)
                short_reason = _sanitize_reason(msg)

                if is_timeout:
                    # Timeout after all retries: NEEDS_REVIEW with short note (no GTEST_SKIP dump)
                    save_draft(
                        gtest_state, draft_key=cid,
                        draft={
                            "full_snippet": (
                                f"// {cid}\n"
                                f"// NEEDS_REVIEW: Copilot API timed out. Retry or edit manually.\n"
                                f"// Reason: {short_reason}\n"
                            ),
                            "code_body": "",
                            "code_status": "NEEDS_REVIEW",
                            "workflow_message": f"API timeout: {short_reason}",
                            "is_fallback_scaffold": True,
                            "is_partial_code": False,
                            "issue_reason": "api_timeout",
                            "fallback_reason": short_reason,
                            "fallback_error_detail": str(msg)[:2000],
                            "missing_context": missing,
                            "generation_source": "COPILOT_BATCH",
                        },
                        engineer_edited=False, wrap_markers=False,
                    )
                    all_results.append({
                        "candidate_id": cid, "ok": False,
                        "workflow_status": "NEEDS_REVIEW", "code_status": "NEEDS_REVIEW",
                        "workflow_message": f"API timeout: {short_reason}",
                        "missing_context": missing,
                    })
                    total_review += 1
                    total_fallback += 1
                else:
                    # Non-timeout API failure: ERROR
                    persist_batch_generation_error(
                        gtest_state, candidate_id=cid, error_message=msg, generation_source="COPILOT_BATCH"
                    )
                    all_results.append({
                        "candidate_id": cid, "ok": False,
                        "workflow_status": "ERROR", "code_status": "ERROR",
                        "workflow_message": msg,
                        "missing_context": missing,
                    })
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
