"""Copilot-first batch GTest generation — orchestrate context, prompts, parse, save."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from web.code_style_samples import load_code_style_samples
from web.copilot_code_writer import (
    extract_testf_fixture_name,
    is_placeholder_testf_fixture,
    normalize_testf_snippet,
    parse_copilot_cpp_response,
    replace_testf_fixture,
)
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

# Smoke test: trivial prompt verifying the Copilot API can parse and echo a [TESTCASE_CODE] block.
_SMOKE_PROMPT = (
    "Return exactly this block. Do not explain.\n\n"
    "[TESTCASE_CODE]\n"
    "testcase_id: TC_API_SMOKE\n"
    "```cpp\n"
    "TEST_F(DummyFixture, TC_API_SMOKE)\n{\n"
    "    EXPECT_THAT(1, Eq(1));\n}\n"
    "```\n"
)
_SMOKE_VARIANTS: list[dict[str, Any]] = [
    {"name": "fresh",    "reuse_session_conversation": False, "persist_conversation": False},
    {"name": "reuse",    "reuse_session_conversation": True,  "persist_conversation": True},
    {"name": "no_reuse", "reuse_session_conversation": False, "persist_conversation": True},
]

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
    r"testcase_id\s*:\s*([A-Za-z0-9_]+)[^\n]*(?:\n(?!```).*){0,5}\n```(?:cpp|c\+\+)?\s*\n([\s\S]*?)```",
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


_CATEGORY_TO_API_CLASS: dict[str, str] = {
    "m365_graph_timeout": "API_TIMEOUT",
    "m365_not_entitled": "API_NOT_ENTITLED",
    "m365_not_ready": "API_AUTH_REQUIRED",
    "m365_missing_scopes": "API_AUTH_MISSING_SCOPES",
    "api_chat_500_conversation_object": "API_500_CONVERSATION_OBJECT",
    "graph_network": "API_NETWORK_ERROR",
    "m365_ssl": "API_SSL_ERROR",
    "m365_copilot_api": "API_COPILOT_ERROR",
}


def _error_category_to_api_class(category: str) -> str:
    return _CATEGORY_TO_API_CLASS.get(str(category or ""), "API_UNKNOWN_ERROR")


def _persist_api_failure(
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    error_message: str,
    api_result_class: str,
    issue_reason: str,
    generation_source: str = "COPILOT_BATCH",
    missing_context: list[dict[str, str]] | None = None,
) -> None:
    """Store an API failure as metadata only — never generates TEST/GTEST_SKIP scaffold code.

    If the candidate already has a draft with real TEST_F code, that code is preserved
    so the user does not lose previously approved work. The failure metadata is updated
    alongside the preserved code.
    """
    cid = str(candidate_id or "").strip()
    if not cid:
        return
    prev = (gtest_state.get("drafts") or {}).get(cid) or {}
    prev_full = str(prev.get("full_snippet") or "").strip()
    prev_has_testf = bool(re.search(r"\bTEST(?:_F)?\s*\(", prev_full)) if prev_full else False
    draft: dict[str, Any] = {
        "full_snippet": prev_full if prev_has_testf else "",
        "code_body": str(prev.get("code_body") or "") if prev_has_testf else "",
        "spec_comment_block": str(prev.get("spec_comment_block") or "") if prev_has_testf else "",
        "code_status": "NEEDS_REVIEW",
        "workflow_message": str(error_message or "")[:500],
        "api_error_message": str(error_message or "")[:2000],
        "api_result_class": api_result_class,
        "is_fallback_scaffold": False,
        "is_partial_code": bool(prev.get("is_partial_code")) if prev_has_testf else False,
        "issue_reason": issue_reason,
        "generation_source": generation_source,
    }
    if missing_context is not None:
        draft["missing_context"] = missing_context
    save_draft(gtest_state, draft_key=cid, draft=draft, engineer_edited=False, wrap_markers=prev_has_testf)


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
        "- If a required API is unknown, return [MISSING_CONTEXT] for this testcase — do not invent\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )


def analyze_missing_generation_context(
    row: dict[str, Any],
    gtest_state: dict[str, Any],
    group_mapping: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Detect what project context is missing for generating code for this testcase.

    Returns a list of missing-item dicts so the user can add rules via Quick Add
    before or after generation. Does NOT block generation.
    """
    from web.project_testcode_memory import _section_body, _signals_in_condition_entries, _strip_md_escapes
    from web.test_group_context import get_group_context_for_row

    items: list[dict[str, str]] = []
    expected_input = str(row.get("expected_input") or "")
    expected_output = str(row.get("expected_output") or "")
    cache = gtest_state.get("project_code_config_cache") or {}
    memory = str(cache.get("project_testcode_memory.md") or "")
    # Normalize markdown backslash escapes (WMODE\_CMD → WMODE_CMD) for reliable substring matching.
    memory_norm = _strip_md_escapes(memory)
    memory_upper = memory_norm.upper()

    # Group context: per-group fixture/namespace takes priority over global rules
    group_ctx = get_group_context_for_row(row, memory)
    group_fixture = (group_ctx.get("fixture_class") or "").strip() if group_ctx else ""
    group_namespace = (group_ctx.get("namespace") or "").strip() if group_ctx else ""
    group_main_fn = (group_ctx.get("main_function") or "").strip() if group_ctx else ""

    # Also check group mapping JSON for suggested_fixture_class and default_main_function.
    # Use _resolve_group_id so rows without group_id (raw preview rows) still resolve correctly.
    if group_mapping:
        _gid = _resolve_group_id(row, group_mapping)
        if _gid:
            _grp = ((group_mapping or {}).get("groups") or {}).get(_gid)
            if _grp:
                if not group_fixture:
                    group_fixture = str(_grp.get("suggested_fixture_class") or "").strip()
                if not group_main_fn:
                    group_main_fn = str(_grp.get("default_main_function") or "").strip()

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

    # Fixture — group context takes priority; fall back to global memory check
    if group_fixture:
        has_fixture = True
    else:
        fixture_body = _section_body(memory, "Fixture / Test Style")
        has_fixture = (
            bool(re.search(r"\bTEST_F\b", memory_norm))
            or bool(re.search(r"fixture\s*(class|name)\s*:", memory_norm, re.I))
            or bool(re.search(r"use\s+fixture\s+`?\w+`?", memory_norm, re.I))
            or (bool(fixture_body) and any(
                l.strip() and not l.strip().startswith("#")
                for l in fixture_body.splitlines()
            ))
        )
    if not has_fixture:
        items.append({
            "type": "missing_fixture",
            "signal": "",
            "description": "No fixture class defined in Project Test Code Memory",
            "suggested_action": "Add Fixture / Test Style Rule",
            "rule_type": "fixture_style",
        })

    # Signals in condition: entries provide signal coverage too
    input_body = _section_body(memory, "Input Mock Pattern")
    output_body = _section_body(memory, "Output Assertion Pattern")
    input_cond_sigs = _signals_in_condition_entries(input_body)
    output_cond_sigs = _signals_in_condition_entries(output_body)

    # Input signals from Given: SIGNAL=value
    for sig in dict.fromkeys(re.findall(r"Given:\s*(\w+)\s*=", expected_input, re.I)):
        sig_up = sig.upper()
        covered = (
            sig_up in memory_upper
            or "RTE_READ_" + sig_up in memory_upper
            or sig_up in input_cond_sigs
        )
        if not covered:
            items.append({
                "type": "missing_input_mock_api",
                "signal": sig,
                "description": f"No input mock / RTE API mapping for signal {sig}",
                "suggested_action": f"Add Input/Mock Rule for {sig}",
                "rule_type": "input_mock",
            })

    # Output signals from Then: SIGNAL=value
    for sig in dict.fromkeys(re.findall(r"Then:\s*(\w+)\s*=", expected_output, re.I)):
        sig_up = sig.upper()
        covered = sig_up in memory_upper or sig_up in output_cond_sigs
        if not covered:
            items.append({
                "type": "missing_output_assertion",
                "signal": sig,
                "description": f"No output assertion variable/API for {sig}",
                "suggested_action": f"Add Output/Assertion Rule for {sig}",
                "rule_type": "output_assertion",
            })

    # Timing — group main_function (e.g. "igsw_Main_Run()") also covers the timing pattern
    has_timing_spec = bool(re.search(r"(?:elapsed|T\s*=\s*\d+|wait|cycle|ms|step)", expected_input, re.I))
    has_timing_memory = bool(re.search(r"igsw_Main_Run|RunForMs|WaitMs|Timing Pattern", memory_norm, re.I)) or bool(
        re.search(r"igsw_Main_Run|RunForMs|WaitMs", group_main_fn, re.I)
    )
    if has_timing_spec and not has_timing_memory:
        items.append({
            "type": "missing_timing_pattern",
            "signal": "",
            "description": "Timing/cycle pattern referenced in testcase but not in memory",
            "suggested_action": "Add Timing Rule (e.g. igsw_Main_Run cycle pattern)",
            "rule_type": "timing",
        })

    return items


def _strip_fixture_from_rules_text(rules_text: str) -> str:
    """Remove the Fixture: section from a relevant-rules block when group context provides the fixture.

    The relevant-rules text is a sequence of sections joined by double-newlines, e.g.:
        "Fixture:\\nline1\\nline2\\n\\nInput Mock Pattern:\\n..."
    Split on double-newlines and drop any block whose header starts with "Fixture:".
    """
    if not rules_text:
        return rules_text
    blocks = rules_text.split("\n\n")
    filtered = [b for b in blocks if not b.lstrip().startswith("Fixture:")]
    return "\n\n".join(filtered)


_TRYTOX_RE = re.compile(r"TryTo[A-Za-z0-9_]+")
_GROUP_ID_RE = re.compile(r"^G0*(\d+)$", re.I)


def _resolve_group_id(row: dict[str, Any], group_mapping: dict[str, Any] | None) -> str:
    """Return the group_id for a row.

    Resolution order:
    1. row.group_id (direct)
    2. key_to_group_id[normalize_group_key(test_function, test_group)]
    3. scan each group's candidate_ids list for this row's candidate_id

    Rows from batch_target_resolution (ordered_preview_rows) never carry group_id,
    so fallbacks 2 and 3 ensure group fixture is always found when the mapping exists.
    """
    gid = str(row.get("group_id") or "")
    if gid:
        return gid
    if not group_mapping:
        return ""

    # Fallback 2: key_to_group_id lookup via test_function + test_group
    key_to_gid = group_mapping.get("key_to_group_id") or {}
    if key_to_gid:
        from web.testcase_group_mapping import normalize_group_key as _ngk
        tf = str(row.get("test_function") or "").strip()
        tg = str(row.get("test_group") or "").strip()
        if tf or tg:
            found = str(key_to_gid.get(_ngk(tf, tg)) or "")
            if found:
                return found

    # Fallback 3: scan candidate_ids in each group (handles stale/missing key_to_group_id)
    cid = str(row.get("candidate_id") or "").strip()
    if cid:
        groups = group_mapping.get("groups") or {}
        for grp_id, grp in groups.items():
            if cid in (grp.get("candidate_ids") or []):
                return grp_id

    return ""


def _cleanup_placeholder_fixtures_from_prompt(
    prompt: str,
    real_fixtures: set[str],
) -> tuple[str, dict[str, Any]]:
    """Post-assembly cleanup: remove lines containing TryTo_xxx placeholder fixture names.

    After per-TC stripping of Fixture: from RELEVANT CONFIRMED RULES, the critical_map
    (PROJECT RULES OVERVIEW) may still contain old memory fixture lines with auto-generated
    TryTo names.  This removes those lines from the full assembled prompt.

    A line is removed only when ALL TryTo patterns on that line are placeholders (not real
    group fixtures).  Lines that contain a real fixture name are kept intact.
    """
    _empty_diag: dict[str, Any] = {
        "prompt_contains_placeholder_fixture": False,
        "placeholder_fixture_removed_count": 0,
        "placeholder_fixture_examples_removed": [],
    }
    if not real_fixtures or not prompt:
        return prompt, _empty_diag

    all_found: set[str] = set(_TRYTOX_RE.findall(prompt))
    placeholder_set = all_found - real_fixtures
    if not placeholder_set:
        return prompt, _empty_diag

    removed_count = 0
    removed_examples: list[str] = []
    new_lines: list[str] = []

    for line in prompt.split("\n"):
        line_trytox = set(_TRYTOX_RE.findall(line))
        placeholders_in_line = line_trytox - real_fixtures
        real_in_line = line_trytox & real_fixtures
        if placeholders_in_line and not real_in_line:
            removed_count += 1
            if len(removed_examples) < 5:
                removed_examples.append(line.strip()[:100])
        else:
            new_lines.append(line)

    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(new_lines))

    remaining_placeholders = set(_TRYTOX_RE.findall(cleaned)) - real_fixtures
    return cleaned, {
        "prompt_contains_placeholder_fixture": bool(remaining_placeholders),
        "placeholder_fixture_removed_count": removed_count,
        "placeholder_fixture_examples_removed": removed_examples,
    }


def _format_missing_context_for_prompt(missing_items: list[dict[str, str]]) -> str:
    """Format missing context list as a compact prompt hint — tells Copilot to return MISSING_CONTEXT."""
    if not missing_items:
        return ""
    lines = [
        "DETECTED MISSING CONTEXT for this testcase "
        "(if any item below is required for correct code, return [MISSING_CONTEXT] — "
        "do NOT invent APIs, do NOT put TODO_REVIEW placeholders for missing required mappings):"
    ]
    for item in missing_items:
        sig = item.get("signal") or ""
        sig_str = f" for `{sig}`" if sig else ""
        lines.append(f"- {item.get('type','').replace('_',' ')}{sig_str}: {item.get('description','')}")
    return "\n".join(lines) + "\n\n"


def _extract_generation_critical_map(memory_content: str, *, char_limit: int = 800) -> str:
    """Extract the highest-value sections from memory for the global prompt overview.

    Supports both * and - bullet styles and condition/code YAML entries.
    Returns a compact string suitable for the required prompt header.
    """
    from web.project_testcode_memory import _section_body, _strip_md_escapes

    text = _strip_md_escapes(str(memory_content or "")).strip()
    if not text:
        return ""

    priority_sections = [
        "Test Design Comment Rule",
        "Fixture / Test Style",
        "Spec Signal to Test Code Map",
        "Fixture / Observable Variables",
        "RTE API Map",
        "Input Mock Pattern",
        "Output Assertion Pattern",
        "Timing Pattern",
        "Default Mock Behavior",
        "Constants / Value Map",
        "Reviewer Notes / Learned Fixes",
    ]

    parts: list[str] = []
    for section in priority_sections:
        body = _section_body(text, section)
        if not body:
            continue
        # Extract both * and - bullet lines (condition: lines count as bullets too)
        # Test Design Comment Rule gets more bullets (it's a multi-line rule, not signal data)
        limit = 8 if section == "Test Design Comment Rule" else 4
        bullets = [
            l.strip() for l in body.splitlines()
            if l.strip() and (
                l.strip().startswith("-") or l.strip().startswith("*")
            ) and l.strip() not in ("-", "*")
        ][:limit]
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

    _raw_memory = str((gtest_state.get("project_code_config_cache") or {}).get("project_testcode_memory.md") or "")
    if not _raw_memory.strip():
        # Fallback: cache wasn't synced before this call (e.g. task runner started before sync).
        # Load global memory directly so relevant rules are always available for the prompt.
        from web.project_testcode_memory import load_global_memory
        _raw_memory = load_global_memory()
    return {
        "sample_blocks": sample_blocks,
        "saved_examples": saved_examples,
        "exemplar": exemplar,
        "reference_snippets": ref_snippets[: (1 if slim_prompt else 4)],
        "folder_files": folder_notes[: (6 if slim_prompt else 30)],
        "testcode_memory": _testcode_memory_block(gtest_state, slim_prompt=slim_prompt),
        # raw_memory: unprocessed cache content used for analysis and per-TC relevant rules
        "raw_memory": _raw_memory,
        "style_example_snippet": style_snippet,
        "style_example_label": style_label,
        "project_instruction": _project_instruction_block(gtest_state, slim_prompt=slim_prompt),
        "spec_context": _bundle_spec_context(bundle, language=language),
        "config_hints": _optional_config_hints(gtest_state, slim_prompt=slim_prompt),
        "language": language,
        "slim_prompt": bool(slim_prompt),
        # Compact critical map (global overview) — kept for required_head so memory appears before instruction
        "critical_map": _extract_generation_critical_map(
            _raw_memory,
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
    group_mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    # --- Shared resolved memory for analysis and per-TC rules ---
    # Use raw (unprocessed) cache memory so fixture/signal sections are never truncated away.
    from web.project_testcode_memory import extract_relevant_rules_for_testcase, memory_diagnostics

    raw_memory = str(context.get("raw_memory") or "")
    _ctx_cache_raw = {"project_testcode_memory.md": raw_memory}
    _ctx_gstate_raw = {"project_code_config_cache": _ctx_cache_raw}

    # Memory diagnostics line (compact, shown once before TESTCASES)
    _mem_diag = memory_diagnostics(raw_memory) if raw_memory else {}
    _mem_diag_line = (
        f"MEMORY: src={_mem_diag.get('source', 'global')} | "
        f"chars={_mem_diag.get('chars', 0)} | "
        f"fixture={'yes' if _mem_diag.get('fixture_found') else 'no'} | "
        f"input rules={_mem_diag.get('input_rules', 0)} | "
        f"output rules={_mem_diag.get('output_rules', 0)}\n\n"
        if _mem_diag else ""
    )

    # --- Target rows + per-TC relevant rules and filtered missing context ---
    # rules_char_limit: enough to hold fixture + test design comment + 3-4 signal code blocks.
    # Use budget-aware limit so rules are not truncated even in slim mode.
    target_chars = 700 if slim_prompt else 2000
    rules_char_limit = max(1200, budget // 3)
    targets_block: list[str] = []
    tc_diagnostics: list[dict[str, Any]] = []
    _gmap_groups: dict[str, Any] = (group_mapping or {}).get("groups") or {}
    _gmap_total = group_mapping.get("total_groups") or len(_gmap_groups) if group_mapping else 0
    for row in target_rows:
        cid = str(row.get("candidate_id") or "")
        event = str(row.get("event") or row.get("test_function") or "").strip()
        operation = str(row.get("operation") or "").strip()
        _row_test_function = str(row.get("test_function") or "").strip()
        _row_event_raw = str(row.get("event") or "").strip()

        # Group mapping lookup: per-TC fixture/namespace/main_function.
        # Use _resolve_group_id so rows without group_id (raw preview rows from
        # batch_target_resolution) still resolve via normalized test_function+event key.
        _raw_row_gid = str(row.get("group_id") or "")
        gid = _resolve_group_id(row, group_mapping)
        grp = _gmap_groups.get(gid) if gid else None
        group_ctx_block = ""
        _tc_fixture = ""
        _tc_namespace = ""
        _tc_main_fn = ""
        if grp:
            _tc_fixture = str(grp.get("suggested_fixture_class") or "").strip()
            _tc_namespace = str(grp.get("suggested_namespace") or "").strip()
            _tc_main_fn = str(grp.get("default_main_function") or "").strip()
            _ctx_lines = ["EXACT GROUP CONTEXT — use these values directly, do NOT return MISSING_CONTEXT for them:"]
            _ctx_lines.append(f"  Group ID: {gid}")
            if _tc_fixture:
                _ctx_lines.append(f"  Fixture class: {_tc_fixture}  [use in TEST_F({_tc_fixture}, <name>)]")
            if _tc_namespace:
                _ctx_lines.append(f"  Namespace: {_tc_namespace}")
            if _tc_main_fn:
                _ctx_lines.append(f"  Main function: {_tc_main_fn}  [call in test body]")
            group_ctx_block = "\n".join(_ctx_lines) + "\n\n"
            # Authoritative direct fixture declaration — prevents Copilot from returning
            # MISSING_CONTEXT for fixture or deriving it from transition/test-function names.
            if _tc_fixture:
                group_ctx_block += (
                    f"EXACT FIXTURE CLASS FOR THIS TESTCASE:\n"
                    f"TEST_F({_tc_fixture}, {cid})\n"
                    f"Use exactly: TEST_F({_tc_fixture}, {cid}) {{ ... }}\n"
                    f"Do NOT search or infer fixture from test name, event, transition rules, "
                    f"or any other source. Use only the fixture provided above.\n"
                    f"Do NOT return [MISSING_CONTEXT] for fixture — it is resolved from Group Mapping.\n\n"
                )

        # Extract per-TC relevant rules (exact condition/code blocks) from raw memory
        rules_result = extract_relevant_rules_for_testcase(
            raw_memory,
            str(row.get("expected_input") or ""),
            str(row.get("expected_output") or ""),
            char_limit=rules_char_limit,
        )
        relevant_text = rules_result.get("text", "") if isinstance(rules_result, dict) else ""
        rules_fixture = rules_result.get("fixture_found", False) if isinstance(rules_result, dict) else False
        rules_in_matched = rules_result.get("input_signals_matched", set()) if isinstance(rules_result, dict) else set()
        rules_out_matched = rules_result.get("output_signals_matched", set()) if isinstance(rules_result, dict) else set()

        # When group provides fixture, strip the global Fixture: section from relevant rules to
        # prevent the memory fixture from conflicting with the EXACT GROUP CONTEXT.
        _filtered_global_fixture = False
        if _tc_fixture and relevant_text:
            _stripped = _strip_fixture_from_rules_text(relevant_text)
            if _stripped != relevant_text:
                _filtered_global_fixture = True
            relevant_text = _stripped
            # If fixture was the only content, rules_fixture is no longer valid
            if _filtered_global_fixture:
                rules_fixture = False

        # Analyze missing context using raw memory (not truncated processed version)
        missing = analyze_missing_generation_context(row, _ctx_gstate_raw, group_mapping=group_mapping)

        # Remove items already covered by matched relevant rules — eliminates contradictions
        filtered_missing = []
        for item in missing:
            t = item.get("type", "")
            sig = (item.get("signal") or "").upper()
            if t == "missing_fixture" and rules_fixture:
                continue
            if t == "missing_input_mock_api" and sig in rules_in_matched:
                continue
            if t == "missing_output_assertion" and sig in rules_out_matched:
                continue
            filtered_missing.append(item)

        relevant_block = f"RELEVANT CONFIRMED RULES:\n{relevant_text}\n\n" if relevant_text else ""
        missing_hint = _format_missing_context_for_prompt(filtered_missing) if filtered_missing else ""
        # Compact mandatory comment instruction — always present regardless of memory content.
        # Operation is namespace metadata only — never goes into When or code body.
        comment_instruction = (
            f"COMMENT: Start TEST_F with a block comment containing: "
            f"testcase_id={cid}"
            + (f", event={event}" if event else "")
            + ", Test design/purpose, Given, Then. "
            "Omit When unless testcase has an explicit executable When field in expected_input. "
            "NOT just // testcase_id.\n"
        )
        # EXACT GROUP CONTEXT is placed after RELEVANT CONFIRMED RULES so it takes final precedence.
        # Operation is intentionally excluded — it is NAMESPACE METADATA only, not executable spec.
        _tc_entry = (
            f"testcase_id: {cid}\n"
            + (f"event: {event}\n" if event else "")
            + f"Given (expected_input):\n{_clip(row.get('expected_input'), target_chars)}\n"
            + f"Then (expected_output):\n{_clip(row.get('expected_output'), target_chars)}\n"
            + comment_instruction
            + (relevant_block if relevant_block else "")
            + (group_ctx_block if group_ctx_block else "")
            + (missing_hint if missing_hint else "")
        )
        targets_block.append(_tc_entry)
        _gnum_m = _GROUP_ID_RE.match(gid) if gid else None
        _display_id = f"TestGroup{int(_gnum_m.group(1))}_{cid}" if _gnum_m else cid
        tc_diagnostics.append({
            # Row resolution tracing
            "candidate_id": cid,
            "display_id": _display_id,
            "row_group_id": _raw_row_gid,
            "row_test_function": _row_test_function,
            "row_event": _row_event_raw,
            "resolved_group_id": gid,
            "group_mapping_loaded_total_groups": _gmap_total,
            "group_mapping_has_resolved_group": bool(grp),
            "resolved_group_fixture": _tc_fixture,
            "resolved_group_namespace": _tc_namespace,
            "resolved_group_main_function": _tc_main_fn,
            # Prompt content flags
            "testcase_id": cid,
            "group_id": gid,
            "group_fixture_used": _tc_fixture,
            "group_namespace_used": _tc_namespace,
            "group_main_function_used": _tc_main_fn,
            "filtered_global_fixture_pattern": _filtered_global_fixture,
            "prompt_contains_TryTo_xxx": "TryTo" in _tc_entry,
            "prompt_contains_GROUP_CONTEXT": bool(group_ctx_block),
            "prompt_contains_group_fixture": bool(_tc_fixture),
            "prompt_contains_exact_fixture": bool(_tc_fixture and group_ctx_block),
            # Operation-column semantics diagnostics
            "operation_used_for_namespace_only": bool(operation),
            "operation_injected_into_code": False,
            "main_function_injected": bool(_tc_main_fn),
            "code_inputs_source": "expected_input",
            "code_outputs_source": "expected_output",
            # backward-compat aliases
            "prompt_fixture_class": _tc_fixture,
            "prompt_namespace": _tc_namespace,
            "prompt_main_function": _tc_main_fn,
            "prompt_contains_group_context": bool(group_ctx_block),
        })

    # --- Style example (compact, high-score only as required) ---
    _style_chars = 600 if slim_prompt else 2000
    raw_style_snippet = str(context.get("style_example_snippet") or "").strip()
    _style_score = _style_example_score(raw_style_snippet)
    _style_is_required = _style_score > 1
    style_snippet = _clip(raw_style_snippet, _style_chars) if raw_style_snippet else ""
    style_label = str(context.get("style_example_label") or "")
    style_example_block = build_style_example_block(style_snippet, label=style_label) if (style_snippet and _style_is_required) else ""
    style_example_optional = build_style_example_block(style_snippet, label=style_label) if (style_snippet and not _style_is_required) else ""

    # --- Project rules overview (critical map — stays in required_head so memory precedes instruction) ---
    critical_map = str(context.get("critical_map") or "").strip()
    critical_map_block = (
        "PROJECT RULES OVERVIEW (use this when writing code):\n"
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

    # --- Compact rules ---
    rules = (
        "RULES:\n"
        "1. Use RELEVANT CONFIRMED RULES per testcase for exact input/output API/assertion.\n"
        "2. Follow the STYLE EXAMPLE structure exactly.\n"
        "3. Do NOT invent API names. Do NOT fill unknown APIs with TODO_REVIEW placeholders.\n"
        "4. If required API/mapping is missing, return MISSING_CONTEXT for that testcase.\n"
        "5. Generate real code only when fixture, input API, and output variable are known.\n"
        "6. UNRESOLVED only if testcase has zero Given/When/Then content.\n"
        "7. EXACT GROUP CONTEXT overrides global fixture: when a testcase has EXACT GROUP CONTEXT, "
        "its Fixture class IS the fixture name — generate TEST_F(fixture_class, <name>) { } and "
        "do NOT return MISSING_CONTEXT for fixture or main function.\n"
        "8. Operation is NAMESPACE METADATA ONLY — never generate code from it, never put it in "
        "// When: comment. Code body must be based only on Given (expected_input) and Then "
        "(expected_output). Omit // When: unless testcase has an explicit executable When field.\n"
        "9. FIXTURE = GROUP MAPPING ONLY. Do NOT infer fixture from test name, event, transition "
        "rules, state-machine conventions, or any source other than EXACT GROUP CONTEXT. "
        "If EXACT GROUP CONTEXT has fixture class → use it, never MISSING_CONTEXT for fixture. "
        "If no fixture in EXACT GROUP CONTEXT → MISSING_CONTEXT for FIXTURE.\n\n"
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
        f"{_mem_diag_line}"
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
    prompt_str = _budget_join(
        required_parts=[required_head],
        optional_parts=optional_parts,
        tail_parts=[tail],
        budget=budget,
    )

    # Post-assembly cleanup: remove placeholder TryTo_xxx fixture lines from the full prompt.
    # The critical_map (PROJECT RULES OVERVIEW) is built from raw memory and may include old
    # auto-generated fixture names (e.g. from Fixture / Test Style) that conflict with the
    # authoritative EXACT GROUP CONTEXT injected per-TC.
    real_fixtures: set[str] = {
        d["group_fixture_used"] for d in tc_diagnostics if d.get("group_fixture_used")
    }
    _cleanup_diag: dict[str, Any] = {}
    if real_fixtures:
        prompt_str, _cleanup_diag = _cleanup_placeholder_fixtures_from_prompt(prompt_str, real_fixtures)

    # Update per-TC diagnostics with post-cleanup prompt state.
    _remaining_trytox = set(_TRYTOX_RE.findall(prompt_str))
    for diag in tc_diagnostics:
        _rf = {diag.get("group_fixture_used") or ""}  - {""}
        diag["prompt_contains_TryTo_xxx"] = bool(_remaining_trytox - _rf) if _rf else bool(_remaining_trytox)
        diag["prompt_contains_placeholder_fixture"] = _cleanup_diag.get("prompt_contains_placeholder_fixture", False)
        diag["placeholder_fixture_removed_count"] = _cleanup_diag.get("placeholder_fixture_removed_count", 0)
        diag["placeholder_fixture_examples_removed"] = _cleanup_diag.get("placeholder_fixture_examples_removed", [])

    return {"prompt": prompt_str, "tc_diagnostics": tc_diagnostics}


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
            + f"Given:\n{_clip(row.get('expected_input'), 500)}\n"
            + f"Then:\n{_clip(row.get('expected_output'), 500)}"
        )
    critical_section = f"CRITICAL MAP:\n{_clip(critical_map, 500)}\n\n" if critical_map else ""
    return _clip(
        f"TASK: Generate real project-style TEST_F per testcase (fast retry, {len(target_rows)} TC).\n"
        "RULES: Use fixture/API from CRITICAL MAP. Do NOT invent API names. "
        "If API/mapping unknown, return MISSING_CONTEXT. No UNRESOLVED unless content is empty. "
        "Fixture source is Group Mapping ONLY — do NOT infer fixture from test name, event, "
        "transition rules, or any other source. If EXACT GROUP CONTEXT provides a fixture class, "
        "use it exactly and do NOT return MISSING_CONTEXT for fixture. "
        "Each TEST_F must open with a full block comment (testcase_id, event, Test design, Given, Then) — "
        "omit When unless testcase has explicit executable When field — not just // testcase_id.\n\n"
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


def build_copilot_unresolved_retry_prompt(
    row: dict[str, Any],
    gtest_state: dict[str, Any],
) -> str:
    """Generation-only retry prompt for UNRESOLVED when the original prompt was complete.

    Explicitly states all code mappings are confirmed and forbids UNRESOLVED.
    Precondition/comment-only Given items must be treated as comments, not blockers.
    """
    from web.project_testcode_memory import extract_relevant_rules_for_testcase

    cid = str(row.get("candidate_id") or "")
    event = str(row.get("event") or row.get("test_function") or "").strip()
    raw_memory = str((gtest_state.get("project_code_config_cache") or {}).get("project_testcode_memory.md") or "")

    rules_result = extract_relevant_rules_for_testcase(
        raw_memory,
        str(row.get("expected_input") or ""),
        str(row.get("expected_output") or ""),
        char_limit=2000,
    )
    relevant_text = rules_result.get("text", "") if isinstance(rules_result, dict) else ""
    confirmed_block = f"CONFIRMED CODE MAPPINGS (use exactly as-is):\n{relevant_text}\n\n" if relevant_text else ""

    comment_instruction = (
        f"COMMENT: Start TEST_F with a block comment: testcase_id={cid}"
        + (f", event={event}" if event else "")
        + ", Test design/purpose, Given, Then. Omit When unless testcase has explicit executable When.\n\n"
    )

    return _clip(
        f"TASK: Generate exactly one TEST_F for testcase_id={cid}.\n\n"
        "IMPORTANT: This testcase has complete executable code mappings confirmed present. "
        "ALL required fixture, input mock API (EXPECT_CALL), and output assertion (EXPECT_THAT) are in the CONFIRMED CODE MAPPINGS below. "
        "You MUST generate code. Do NOT return [UNRESOLVED] or [MISSING_CONTEXT]. "
        "Precondition or annotation-only items in Given are comments — they do NOT block generation.\n\n"
        f"testcase_id: {cid}\n"
        + (f"event: {event}\n" if event else "")
        + f"Given/When (expected_input):\n{_clip(row.get('expected_input'), 600)}\n\n"
        + f"Then (expected_output):\n{_clip(row.get('expected_output'), 600)}\n\n"
        + confirmed_block
        + comment_instruction
        + "OUTPUT — return only:\n"
        "[TESTCASE_CODE]\n"
        f"testcase_id: {cid}\n"
        "```cpp\n<real TEST_F using fixture and APIs from CONFIRMED CODE MAPPINGS above>\n```\n",
        4000,
    )


def build_copilot_fixture_retry_prompt(
    row: dict[str, Any],
    fixture: str,
) -> str:
    """Minimal retry prompt for fixture-only MISSING_CONTEXT.

    Used when the first pass returned MISSING_CONTEXT only for fixture but the group
    mapping already resolves the fixture.  States the exact fixture class unambiguously
    so Copilot cannot return MISSING_CONTEXT for it again.
    """
    cid = str(row.get("candidate_id") or "")
    event = str(row.get("event") or row.get("test_function") or "").strip()
    return _clip(
        f"TASK: Generate exactly one TEST_F for testcase_id={cid}.\n\n"
        f"EXACT FIXTURE FROM GROUP MAPPING (authoritative — do NOT ignore):\n"
        f"TEST_F({fixture}, {cid})\n"
        f"Fixture source: Group Mapping only. Do NOT search, infer, or derive fixture from "
        f"test name, event, transition rules, state-machine naming, or any other source.\n"
        f"Use exactly this fixture class. Do NOT return [MISSING_CONTEXT] for fixture.\n\n"
        f"testcase_id: {cid}\n"
        + (f"event: {event}\n" if event else "")
        + f"Given (expected_input):\n{_clip(row.get('expected_input'), 600)}\n\n"
        + f"Then (expected_output):\n{_clip(row.get('expected_output'), 600)}\n\n"
        "RULES: Generate real TEST_F code using the exact fixture above. "
        "Return [MISSING_CONTEXT] ONLY if input mock API or output assertion is unknown — "
        "NOT for fixture (fixture is resolved from Group Mapping, provided above). "
        "Do NOT return [UNRESOLVED].\n\n"
        "OUTPUT:\n"
        "[TESTCASE_CODE]\n"
        f"testcase_id: {cid}\n"
        "```cpp\n"
        f"TEST_F({fixture}, {cid})\n"
        "{{\n    // block comment: testcase_id, event, Test design, Given, Then\n    // ...\n}}\n"
        "```\n",
        3000,
    )


def run_copilot_api_smoke_test(
    cfg: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Fire _SMOKE_PROMPT against Copilot API using each session variant.

    Returns the first working mode and all variant diagnostics. Stops on first success.
    Used before UNRESOLVED direct-code retry to discover which API mode is functional.
    """
    variants_tried: list[dict[str, Any]] = []
    working_mode: str | None = None
    working_kwargs: dict[str, Any] | None = None
    t_total = perf_counter()

    for _v in _SMOKE_VARIANTS:
        vname = str(_v["name"])
        vkwargs = {k: v for k, v in _v.items() if k != "name"}
        t0 = perf_counter()
        chat = run_copilot_chat_result(cfg, _SMOKE_PROMPT, user_id=user_id, **vkwargs)
        duration = round(perf_counter() - t0, 2)
        raw = str(chat.get("reply") or chat.get("content") or "")
        has_tc = "[TESTCASE_CODE]" in raw
        has_unres = "[UNRESOLVED]" in raw
        # Detect response-equals-prompt: API echoed request text instead of answering
        _resp_eq_prompt = bool(raw) and raw[:120] == _SMOKE_PROMPT[:120]
        smoke_ok = bool(chat.get("ok")) and has_tc and not _resp_eq_prompt
        if smoke_ok:
            rc = "TESTCASE_CODE"
        elif not chat.get("ok"):
            rc = "TIMEOUT" if str(chat.get("error_category") or "") == "m365_graph_timeout" else "ERROR"
        elif has_unres:
            rc = "UNRESOLVED"
        elif raw.strip():
            rc = "NO_TAG"
        else:
            rc = "EMPTY"
        variants_tried.append({
            "variant": vname,
            "ok": smoke_ok,
            "response_class": rc,
            "raw_response_preview": raw[:300],
            "contains_TESTCASE_CODE": has_tc,
            "contains_UNRESOLVED": has_unres,
            "response_equals_prompt": _resp_eq_prompt,
            "prompt_startswith": _SMOKE_PROMPT[:60],
            "response_startswith": raw[:60],
            "duration": duration,
            "http_status": int(chat.get("graph_status") or 0),
            **vkwargs,
        })
        if smoke_ok and working_mode is None:
            working_mode = vname
            working_kwargs = dict(vkwargs)
            break  # first working variant wins

    return {
        "smoke_ok": working_mode is not None,
        "working_mode": working_mode,
        "working_mode_kwargs": working_kwargs,
        "variants_tried": variants_tried,
        "total_duration": round(perf_counter() - t_total, 2),
    }


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
    group_mapping: dict[str, Any] | None = None,
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
        _built = build_copilot_batch_prompt(
            context,
            rows,
            engineer_note=engineer_note,
            scope_label=scope_label,
            import_group_label=import_group,
            slim_prompt=slim_prompt,
            prompt_budget=prompt_budget,
            group_mapping=group_mapping,
        )
        prompt = _built["prompt"]
        _tc_diag = _built.get("tc_diagnostics") or []
        prompts.append(
            {
                "batch_index": i + 1,
                "batch_count": len(chunks),
                "candidate_ids": chunk,
                "testcase_count": len(chunk),
                "prompt": prompt,
                "char_count": len(prompt),
                "_target_rows": rows,
                "tc_diagnostics": _tc_diag,
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


_RECOVERY_CODE_RE = re.compile(
    r"\b(EXPECT_CALL|EXPECT_THAT|igsw_Main_Run|SetArgPointee|WillRepeatedly|WillOnce)\b"
)


def _build_review_draft(
    cid: str,
    row: dict[str, Any],
    raw_memory: str,
    group_fixture: str,
    missing_context_items: list[dict[str, Any]] | None = None,
) -> str:
    """Build a LOCAL_REVIEW_DRAFT snippet using maximum known code from project memory.

    Uses exact EXPECT_CALL/EXPECT_THAT patterns from memory for known signals.
    Inserts // ALEX_REVIEW: comments for unknown inputs, outputs, or missing fixture.
    Never invents APIs, fixture names, helper functions, or fake code.
    Never uses GTEST_SKIP, AutoFixture, or TEST(AlexGeneratedFallback, ...).
    Returns '' only when cid is empty.
    """
    if not cid:
        return ""

    from web.project_testcode_memory import extract_relevant_rules_for_testcase

    event = str(row.get("event") or row.get("test_function") or "").strip()
    ei = str(row.get("expected_input") or "").strip()
    eo = str(row.get("expected_output") or "").strip()

    # Compact block comment: testcase_id, event, Given, Then (omit When unless explicit)
    comment_parts = [f"testcase_id: {cid}"]
    if event:
        comment_parts.append(f"event: {event}")

    _given = ""
    if ei:
        for _line in ei.splitlines():
            _ls = _line.strip()
            if _ls.lower().startswith("given:"):
                _given = _ls[6:].strip()
                break
        if not _given:
            _given = ei[:200]

    _then = ""
    if eo:
        for _line in eo.splitlines():
            _ls = _line.strip()
            if _ls.lower().startswith("then:"):
                _then = _ls[5:].strip()
                break
        if not _then:
            _then = eo[:200]

    if _given:
        comment_parts.append(f"Given: {_given[:200]}")
    if _then:
        comment_parts.append(f"Then: {_then[:200]}")

    block_comment = "/*\n" + "".join(f" * {p}\n" for p in comment_parts) + " */"

    # Extract known code patterns from project memory
    rules_result = extract_relevant_rules_for_testcase(raw_memory, ei, eo, char_limit=2000)
    rules_text: str = ""
    _input_matched: set[str] = set()
    _output_matched: set[str] = set()
    if isinstance(rules_result, dict):
        rules_text = rules_result.get("text", "") or ""
        _input_matched = rules_result.get("input_signals_matched", set()) or set()
        _output_matched = rules_result.get("output_signals_matched", set()) or set()

    code_lines: list[str] = []
    for _line in rules_text.splitlines():
        _stripped = _line.strip()
        if _stripped and _RECOVERY_CODE_RE.search(_stripped):
            code_lines.append(f"    {_stripped}")

    # Collect signals with explicit MISSING_CONTEXT items from Copilot
    mc = missing_context_items or []
    _fixture_mc = any(str(m.get("missing_type") or "").upper() == "FIXTURE" for m in mc)
    _missing_in = sorted({
        str(m.get("signal_or_item") or m.get("signal") or "").strip()
        for m in mc
        if str(m.get("missing_type") or "").upper() in ("INPUT_API", "INPUT_MOCK_API", "INPUT")
        and str(m.get("signal_or_item") or m.get("signal") or "").strip()
    })
    _missing_out = sorted({
        str(m.get("signal_or_item") or m.get("signal") or "").strip()
        for m in mc
        if str(m.get("missing_type") or "").upper() in ("OUTPUT_ASSERTION", "OUTPUT_ASSERT", "OUTPUT")
        and str(m.get("signal_or_item") or m.get("signal") or "").strip()
    })

    # Also flag signals from spec that memory didn't match
    _ei_unmatched = [s for s in re.findall(r"(?:given|when):\s*(\w+)\s*=", ei, re.I) if s.upper() not in _input_matched]
    _eo_unmatched = [s for s in re.findall(r"then:\s*(\w+)\s*=", eo, re.I) if s.upper() not in _output_matched]
    all_missing_in = sorted({s.upper() for s in _missing_in + _ei_unmatched})
    all_missing_out = sorted({s.upper() for s in _missing_out + _eo_unmatched})

    # Pre-TEST_F ALEX_REVIEW comment when fixture is unknown
    fixture_unknown = not group_fixture or _fixture_mc
    pre_lines: list[str] = []
    if fixture_unknown:
        pre_lines.append("// ALEX_REVIEW: fixture class missing or unresolved — update Group Mapping")

    # Body: known code lines first, then ALEX_REVIEW for missing signals
    body_lines: list[str] = []
    if not ei and eo:
        body_lines.append("    // Given: no explicit input condition in testspec")
    if code_lines:
        body_lines.extend(code_lines)
    for sig in all_missing_in:
        body_lines.append(f"    // ALEX_REVIEW: input mapping missing for {sig}")
    for sig in all_missing_out:
        body_lines.append(f"    // ALEX_REVIEW: output mapping missing for {sig}")
    if not body_lines:
        body_lines = ["    // ALEX_REVIEW: review and fill in implementation"]

    body = "\n".join(body_lines)
    fixture = group_fixture if group_fixture else "ALEX_FIXTURE_MISSING"
    parts = [block_comment] + pre_lines + [f"TEST_F({fixture}, {cid})", "{", body, "}"]
    return "\n".join(parts)


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
    _prompt_chars: int = 0,
    _prompt_preview: str = "",
    _raw_response_preview: str = "",
) -> dict[str, Any]:
    parsed = parse_copilot_batch_response(content)
    unresolved_by_id = dict(parsed.get("unresolved_by_id") or {})
    missing_context_by_id = dict(parsed.get("missing_context_by_id") or {})
    parsed_by_id = {str(i["candidate_id"]): i for i in parsed.get("items") or [] if i.get("candidate_id")}

    _resp_chars = len(content)
    _has_tc_tag = "[TESTCASE_CODE]" in content
    _has_mc_tag = "[MISSING_CONTEXT]" in content
    _parsed_ids = list(parsed_by_id.keys()) + list(unresolved_by_id.keys()) + list(missing_context_by_id.keys())
    _diag_base: dict[str, Any] = {
        "prompt_chars": _prompt_chars,
        "response_chars": _resp_chars,
        "contains_TESTCASE_CODE": _has_tc_tag,
        "contains_MISSING_CONTEXT": _has_mc_tag,
        "parsed_testcase_ids": _parsed_ids,
    }

    if not parsed_by_id and not unresolved_by_id and not missing_context_by_id:
        return {
            "ok": False,
            "error": parsed.get("error") or "No [TESTCASE_CODE], [MISSING_CONTEXT], or [UNRESOLVED] blocks parsed.",
            "parse": parsed,
            "results": [],
            "summary": {"saved": 0, "needs_review": 0, "error": 0, "skipped": 0, "total": 0},
            "api_diag": {**_diag_base, "api_result_class": "NO_TAGS", "parsed_code_chars": 0, "issue_reason": "no_tags_parsed"},
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
    _raw_memory_for_recovery = str(cfg_cache.get("project_testcode_memory.md") or "")

    # Load group mapping once for fixture replacement across all TCs in this batch
    _batch_group_mapping: dict[str, Any] = {}
    if job_output:
        try:
            from pathlib import Path as _Path2
            from web.testcase_group_mapping import load_group_mapping as _lgm2
            _batch_group_mapping = _lgm2(_Path2(str(job_output))) or {}
        except Exception:
            pass
    _batch_gmap_groups: dict[str, Any] = (_batch_group_mapping.get("groups") or {})

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
            mc_items = list(missing_context_by_id[cid])

            # Resolve group fixture for this TC. Suppress FIXTURE missing_context items when
            # the group mapping already provides a fixture — Copilot's MISSING_CONTEXT for
            # fixture means the prompt context wasn't applied, not that the fixture is unknown.
            _mc_row = next(
                (r for r in (gtest_state.get("_batch_target_rows") or []) if str(r.get("candidate_id") or "") == cid),
                {"candidate_id": cid},
            )
            _mc_gid = _resolve_group_id(_mc_row, _batch_group_mapping or None)
            _mc_grp = _batch_gmap_groups.get(_mc_gid) if _mc_gid else None
            _mc_fixture = str((_mc_grp or {}).get("suggested_fixture_class") or "").strip()
            _mc_namespace = str((_mc_grp or {}).get("suggested_namespace") or "").strip()
            _mc_main_fn = str((_mc_grp or {}).get("default_main_function") or "").strip()
            # Never synthesise AutoFixture — only use what Group Mapping explicitly provides.
            _mc_items_all = list(mc_items)  # full list including FIXTURE items (for ALEX_REVIEW)
            if _mc_fixture:
                # Fixture is known from Group Mapping: strip FIXTURE missing-context items
                # (they'll be marked via // ALEX_REVIEW in the draft if truly unresolved).
                mc_items = [m for m in mc_items if str(m.get("missing_type") or "").upper() != "FIXTURE"]

            _gm_diag = {
                "candidate_id": cid,
                "resolved_group_id": _mc_gid,
                "group_mapping_found": bool(_batch_group_mapping),
                "group_fixture_used": _mc_fixture,
                "group_namespace_used": _mc_namespace,
                "used_ALEX_FIXTURE_MISSING": not bool(_mc_fixture),
            }

            # Always build a review draft — never leave the editor empty.
            # Source = LOCAL_REVIEW_DRAFT (ALEX assembled known pieces after Copilot failed).
            _review_draft = _build_review_draft(
                cid, _mc_row, _raw_memory_for_recovery, _mc_fixture,
                missing_context_items=_mc_items_all,
            )
            if _review_draft:
                _only_fixture_missing = not mc_items and bool(_mc_items_all)
                _issue = "fixture_needs_review" if _only_fixture_missing else "missing_generation_context"
                _mc_summary = "; ".join(
                    f"{it.get('missing_type','?')}/{it.get('signal_or_item','?')}"
                    for it in mc_items
                )[:100]
                _msg = (
                    f"Local review draft: {_mc_summary}" if _mc_summary
                    else (f"Fixture review draft — update Group Mapping fixture for {_mc_gid}" if _mc_gid
                          else "Local review draft generated")
                )
                _tc_diag_mc = {
                    **_diag_base,
                    "api_result_class": "MISSING_CONTEXT",
                    "parsed_code_chars": len(_review_draft),
                    "issue_reason": _issue,
                    "resolved_group_id": _mc_gid,
                    "resolved_group_fixture": _mc_fixture,
                    "fixture_suppressed_by_group_mapping": bool(_mc_fixture),
                    "review_draft_used": True,
                    "generation_source": "LOCAL_REVIEW_DRAFT",
                    "group_mapping_diagnostics": _gm_diag,
                }
                save_draft(
                    gtest_state, draft_key=cid,
                    draft={
                        "full_snippet": _review_draft,
                        "code_body": _review_draft,
                        "code_status": "NEEDS_REVIEW",
                        "workflow_message": _msg,
                        "is_fallback_scaffold": True,
                        "is_partial_code": True,
                        "issue_reason": _issue,
                        "missing_context": mc_items,
                        "generation_source": "LOCAL_REVIEW_DRAFT",
                        "api_diag": _tc_diag_mc,
                        "group_mapping_diagnostics": _gm_diag,
                    },
                    engineer_edited=False, wrap_markers=False,
                )
                results.append({
                    "candidate_id": cid,
                    "ok": True,
                    "workflow_status": "NEEDS_REVIEW",
                    "workflow_message": _msg,
                    "code_status": "NEEDS_REVIEW",
                    "issue_reason": _issue,
                    "missing_context": mc_items,
                    "api_diag": _tc_diag_mc,
                })
                needs_review += 1
                continue

            # Fallback when draft could not be built (empty cid — shouldn't happen)
            mc_summary = "; ".join(
                f"{it.get('missing_type','?')}/{it.get('signal_or_item','?')}"
                for it in mc_items
            )[:200]
            msg = f"Copilot MISSING_CONTEXT: {mc_summary}" if mc_items else f"Copilot MISSING_CONTEXT (fixture check required for group {_mc_gid})"
            _tc_diag_mc_fb = {
                **_diag_base,
                "api_result_class": "MISSING_CONTEXT",
                "parsed_code_chars": 0,
                "issue_reason": "missing_generation_context",
                "resolved_group_id": _mc_gid,
                "resolved_group_fixture": _mc_fixture,
                "fixture_suppressed_by_group_mapping": bool(_mc_fixture),
            }
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
                    "api_diag": _tc_diag_mc_fb,
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
                "api_diag": _tc_diag_mc_fb,
            })
            needs_review += 1
            continue

        if cid in unresolved_by_id:
            # UNRESOLVED from Copilot → build LOCAL_REVIEW_DRAFT, never leave editor empty.
            unresolved_reason = str(unresolved_by_id[cid] or "Copilot returned UNRESOLVED for this testcase.")
            row_data = next((r for r in (gtest_state.get("_batch_target_rows") or []) if str(r.get("candidate_id") or "") == cid), {"candidate_id": cid})
            missing = analyze_missing_generation_context(row_data, gtest_state, group_mapping=_batch_group_mapping or None)
            _unres_gid = _resolve_group_id(row_data, _batch_group_mapping or None)
            _unres_grp = _batch_gmap_groups.get(_unres_gid) if _unres_gid else None
            _unres_fixture = str((_unres_grp or {}).get("suggested_fixture_class") or "").strip()
            _unres_namespace = str((_unres_grp or {}).get("suggested_namespace") or "").strip()
            _unres_draft_code = _build_review_draft(
                cid, row_data, _raw_memory_for_recovery, _unres_fixture,
                missing_context_items=missing if isinstance(missing, list) else None,
            )
            _unres_gen_src = "LOCAL_REVIEW_DRAFT" if _unres_draft_code else generation_source
            _unres_gm_diag = {
                "candidate_id": cid,
                "resolved_group_id": _unres_gid,
                "group_mapping_found": bool(_batch_group_mapping),
                "group_fixture_used": _unres_fixture,
                "group_namespace_used": _unres_namespace,
                "used_ALEX_FIXTURE_MISSING": not bool(_unres_fixture),
            }
            _tc_diag_unres = {
                **_diag_base,
                "api_result_class": "UNRESOLVED",
                "parsed_code_chars": len(_unres_draft_code),
                "issue_reason": "unresolved_by_copilot",
                "review_draft_used": bool(_unres_draft_code),
                "generation_source": _unres_gen_src,
                "group_mapping_diagnostics": _unres_gm_diag,
            }
            unres_draft = {
                "full_snippet": _unres_draft_code,
                "code_body": _unres_draft_code,
                "code_status": "NEEDS_REVIEW",
                "workflow_message": f"Copilot UNRESOLVED: {unresolved_reason}",
                "review_reason": unresolved_reason,
                "generation_source": _unres_gen_src,
                "is_fallback_scaffold": bool(_unres_draft_code),
                "is_partial_code": bool(_unres_draft_code),
                "issue_reason": "unresolved_by_copilot",
                "unresolved_copilot_reason": unresolved_reason,
                "missing_context": missing,
                "api_diag": _tc_diag_unres,
                "group_mapping_diagnostics": _unres_gm_diag,
                "api_prompt_preview": str(_prompt_preview)[:500],
                "api_raw_response_preview": str(_raw_response_preview)[:500],
            }
            save_draft(gtest_state, draft_key=cid, draft=unres_draft, engineer_edited=False, wrap_markers=False)
            results.append(
                {
                    "candidate_id": cid,
                    "ok": bool(_unres_draft_code),
                    "workflow_status": "NEEDS_REVIEW",
                    "workflow_message": f"Copilot UNRESOLVED: {unresolved_reason}",
                    "code_status": "NEEDS_REVIEW",
                    "full_snippet": _unres_draft_code,
                    "issue_reason": "unresolved_by_copilot",
                    "missing_context": missing,
                    "api_diag": _tc_diag_unres,
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
            _tc_diag_nf = {**_diag_base, "api_result_class": "NOT_FOUND", "parsed_code_chars": 0, "issue_reason": "testcase_id_not_in_response"}
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                    "api_diag": _tc_diag_nf,
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
            _tc_diag_empty = {**_diag_base, "api_result_class": "EMPTY", "parsed_code_chars": 0, "issue_reason": "empty_code_block"}
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "workflow_status": "ERROR",
                    "workflow_message": msg,
                    "code_status": "ERROR",
                    "api_diag": _tc_diag_empty,
                }
            )
            error += 1
            continue

        if not re.search(r"\bTEST(?:_F)?\s*\(", full):
            # Has content but no TEST_F — keep as NEEDS_REVIEW (not ERROR)
            # Copilot returned something; user can edit it
            msg = "no TEST_F in block — code needs review/edit"
            _tc_diag_notf = {**_diag_base, "api_result_class": "NO_TEST_F", "parsed_code_chars": len(full), "issue_reason": "no_test_f_in_block"}
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
                    "api_diag": _tc_diag_notf,
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
                    "api_diag": _tc_diag_notf,
                }
            )
            needs_review += 1
            continue

        _row_meta = next(
            (r for r in (gtest_state.get("_batch_target_rows") or []) if str(r.get("candidate_id") or "") == cid),
            None,
        )
        full = normalize_testf_snippet(full, _row_meta)

        # --- Fixture replacement ---
        # If generated TEST_F uses a TryTo placeholder that doesn't match the group fixture,
        # replace it.  If placeholder but no group fixture exists, keep NEEDS_REVIEW.
        # Use _resolve_group_id so raw preview rows (no group_id) still find their group.
        _gid_for_fix = _resolve_group_id(_row_meta or {}, _batch_group_mapping or None)
        _grp_for_fix = _batch_gmap_groups.get(_gid_for_fix) if _gid_for_fix else None
        _group_fixture = str((_grp_for_fix or {}).get("suggested_fixture_class") or "").strip()
        _original_fixture = extract_testf_fixture_name(full)
        _final_fixture = _original_fixture
        _fixture_replaced = False
        _auto_fixture_applied = False

        if _original_fixture and _group_fixture and _original_fixture != _group_fixture:
            full = replace_testf_fixture(full, _group_fixture)
            _final_fixture = _group_fixture
            _fixture_replaced = True
        elif _original_fixture and not _group_fixture and is_placeholder_testf_fixture(_original_fixture):
            # Copilot used a placeholder fixture but no group fixture is defined.
            # Keep the generated code as-is (placeholder is clearly not a real class name).
            # Mark NEEDS_REVIEW — user must update Group Mapping and use "Apply to Drafts".
            # Never synthesise AutoFixture_<GroupID>.
            _auto_fixture_applied = True

        _fixture_diag = {
            "original_fixture": _original_fixture,
            "final_fixture": _final_fixture,
            "fixture_replaced_from_group_mapping": _fixture_replaced,
            "auto_fixture_applied": _auto_fixture_applied,
            "group_id": _gid_for_fix,
            "group_fixture_class": _group_fixture,
        }

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
            allow_auto_save=False,
        )
        st = str(wf.get("workflow_status") or wf.get("code_status") or "ERROR")
        _issue_reason = "" if st == "SAVED" else (wf.get("workflow_message") or st)
        if _auto_fixture_applied:
            st = "NEEDS_REVIEW"  # always NEEDS_REVIEW when placeholder fixture was kept
            _issue_reason = "fixture_needs_review"
        _tc_diag_ok = {**_diag_base, "api_result_class": st, "parsed_code_chars": len(full), "issue_reason": _issue_reason}
        saved_draft = (gtest_state.get("drafts") or {}).get(cid)
        if saved_draft is not None:
            saved_draft["api_diag"] = _tc_diag_ok
            if _auto_fixture_applied:
                saved_draft["issue_reason"] = "fixture_needs_review"
                saved_draft["code_status"] = "NEEDS_REVIEW"
                saved_draft["workflow_message"] = (
                    f"Placeholder fixture ({_final_fixture}) — update Group Mapping "
                    "and use 'Apply to Drafts' to replace with the correct fixture"
                )
        persisted_snippet = str((saved_draft or {}).get("full_snippet") or "")
        if st == "SAVED":
            saved += 1
        elif st == "NEEDS_REVIEW":
            needs_review += 1
        else:
            error += 1
        _wf_msg = (
            saved_draft.get("workflow_message") or wf.get("workflow_message") or ""
            if saved_draft else wf.get("workflow_message") or ""
        )
        results.append(
            {
                "candidate_id": cid,
                "ok": st in ("SAVED", "NEEDS_REVIEW"),
                "workflow_status": st,
                "workflow_message": _wf_msg,
                "code_status": st,
                "issue_reason": _issue_reason,
                "generation_source": generation_source,
                "full_snippet": persisted_snippet,
                "api_diag": _tc_diag_ok,
                "fixture_diag": _fixture_diag,
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
        **_diag_base,
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
        "api_diag": _diag_base,
    }


def apply_group_mapping_to_drafts(
    gtest_state: dict[str, Any],
    group_mapping: dict[str, Any],
    *,
    group_id: str | None = None,
) -> dict[str, Any]:
    """Replace TEST_F fixture in existing drafts using the group mapping fixture class.

    For each TC in the specified group (or all groups), finds the draft and replaces
    TEST_F(oldFixture, name) with TEST_F(newFixture, name) using suggested_fixture_class.
    No Copilot call — preserves the test body.  SAVED drafts become NEEDS_REVIEW.

    Returns a summary dict with ``updated``, ``skipped``, ``no_draft`` counts.
    """
    groups = (group_mapping.get("groups") or {})
    target_groups: dict[str, Any] = (
        {group_id: groups[group_id]} if (group_id and group_id in groups) else groups
    )
    drafts = gtest_state.setdefault("drafts", {})
    updated = skipped = no_draft = 0
    detail: list[dict[str, Any]] = []

    for gid, grp in target_groups.items():
        new_fixture = str(grp.get("suggested_fixture_class") or "").strip()
        if not new_fixture:
            for cid in (grp.get("candidate_ids") or []):
                skipped += 1
                detail.append({"candidate_id": cid, "group_id": gid, "status": "no_fixture_in_group"})
            continue

        for cid in (grp.get("candidate_ids") or []):
            draft = drafts.get(cid)
            if not isinstance(draft, dict):
                no_draft += 1
                detail.append({"candidate_id": cid, "group_id": gid, "status": "no_draft"})
                continue

            full = str(draft.get("full_snippet") or draft.get("code_body") or "")
            if not full or not re.search(r"\bTEST(?:_F)?\s*\(", full):
                skipped += 1
                detail.append({"candidate_id": cid, "group_id": gid, "status": "no_test_f"})
                continue

            old_fixture = extract_testf_fixture_name(full)
            if old_fixture == new_fixture:
                skipped += 1
                detail.append({"candidate_id": cid, "group_id": gid, "status": "already_correct", "fixture": new_fixture})
                continue

            new_full = replace_testf_fixture(full, new_fixture)
            # Strip the ALEX_REVIEW fixture-missing comment left by _build_review_draft
            # when ALEX_FIXTURE_MISSING was the placeholder.
            if old_fixture == "ALEX_FIXTURE_MISSING":
                new_full = re.sub(
                    r"^//\s*ALEX_REVIEW:\s*fixture class missing or unresolved[^\n]*\n?",
                    "",
                    new_full,
                    flags=re.MULTILINE,
                )
            draft["full_snippet"] = new_full
            _cb = str(draft.get("code_body") or "")
            if re.search(r"\bTEST(?:_F)?\s*\(", _cb):
                _cb_new = replace_testf_fixture(_cb, new_fixture)
                if old_fixture == "ALEX_FIXTURE_MISSING":
                    _cb_new = re.sub(
                        r"^//\s*ALEX_REVIEW:\s*fixture class missing or unresolved[^\n]*\n?",
                        "",
                        _cb_new,
                        flags=re.MULTILINE,
                    )
                draft["code_body"] = _cb_new
            prev_status = str(draft.get("code_status") or "")
            if prev_status == "SAVED":
                draft["code_status"] = "NEEDS_REVIEW"
                draft["workflow_message"] = (
                    f"Fixture updated from Group Mapping ({old_fixture} → {new_fixture}); review recommended"
                )
            draft.setdefault("api_diag", {})["apply_group_mapping_at"] = _now_iso()
            updated += 1
            detail.append({
                "candidate_id": cid, "group_id": gid, "status": "updated",
                "old_fixture": old_fixture, "new_fixture": new_fixture,
                "was_saved": prev_status == "SAVED",
            })

    return {
        "ok": True,
        "updated": updated,
        "skipped": skipped,
        "no_draft": no_draft,
        "total": updated + skipped + no_draft,
        "detail": detail,
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
    _group_mapping: dict[str, Any] = {}
    if job_output:
        try:
            from pathlib import Path as _Path
            from web.testcase_group_mapping import load_group_mapping as _load_gmap
            _group_mapping = _load_gmap(_Path(str(job_output))) or {}
        except Exception:
            pass
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
        group_mapping=_group_mapping or None,
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
        # Per-prompt diagnostics stored in run state for UI/debugging
        run["last_prompt_diag"] = {
            "api_prompt_chars": len(prompt_for_api),
            "api_prompt_contains_relevant_rules": "RELEVANT CONFIRMED RULES" in prompt_for_api,
            "api_prompt_contains_input_code": "EXPECT_CALL" in prompt_for_api,
            "api_prompt_contains_output_code": "EXPECT_THAT" in prompt_for_api,
            "api_prompt_contains_fixture": any(kw in prompt_for_api for kw in ("Fixture:", "TEST_F(", "Fixture class")),
            "api_prompt_contains_memory_diag": "MEMORY:" in prompt_for_api,
            "api_prompt_contains_group_context": "GROUP CONTEXT" in prompt_for_api,
            "chunk_candidate_ids": list(batch.get("candidate_ids") or []),
            "tc_diagnostics": list(batch.get("tc_diagnostics") or []),
        }
        chat = run_copilot_chat_result(
            cfg,
            prompt_for_api,
            reuse_session_conversation=False,  # fresh conversation per chunk (avoids stale state)
            persist_conversation=False,          # do not persist; each chunk is independent
            user_id=user_id,
        )
        # Store API call diagnostics immediately after each chat call
        run["last_api_call_diag"] = {
            "create_status": chat.get("create_status"),
            "create_payload_keys": chat.get("create_payload_keys") or [],
            "chat_status": chat.get("chat_status"),
            "error_category": str(chat.get("error_category") or ""),
            "conversation_id": str(chat.get("conversation_id") or ""),
            "server_displayName": str(chat.get("server_displayName") or ""),
            "reuse_session_conversation": chat.get("reuse_session_conversation", False),
            "persist_conversation": chat.get("persist_conversation", False),
            "payload_keys": chat.get("payload_keys") or ["message", "locationHint"],
            "response_body_preview": str(chat.get("response_body_preview") or "")[:200],
            "retried_with_fresh_conversation": bool(chat.get("retried_with_fresh_conversation")),
        }
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
                            _prompt_chars=len(_single_prompt),
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
            is_timeout = category == "m365_graph_timeout"
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

                api_class = _error_category_to_api_class(category)
                _persist_api_failure(
                    gtest_state,
                    candidate_id=cid,
                    error_message=short_reason,
                    api_result_class=api_class,
                    issue_reason=category or "api_failure",
                    missing_context=missing,
                )
                all_results.append({
                    "candidate_id": cid, "ok": False,
                    "workflow_status": "NEEDS_REVIEW", "code_status": "NEEDS_REVIEW",
                    "workflow_message": short_reason,
                    "missing_context": missing,
                    "api_result_class": api_class,
                })
                if is_timeout:
                    total_fallback += 1
                total_review += 1
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
        # Detect prompt echo: either extraction layer rejected it (preferred) or raw still matches
        _extraction_failed = str(chat.get("api_result_class") or "") == "API_RESPONSE_EXTRACTION_FAILED"
        _resp_eq_prompt = _extraction_failed or (bool(raw) and bool(prompt_for_api) and raw[:200] == prompt_for_api[:200])
        run["last_response_diag"] = {
            "prompt_startswith": prompt_for_api[:80],
            "response_startswith": raw[:80],
            "response_equals_prompt": _resp_eq_prompt,
            "extraction_failed": _extraction_failed,
            "rejected_prompt_echo_count": chat.get("rejected_prompt_echo_count", 0),
            "extracted_message_index": chat.get("extracted_message_index"),
            "extracted_message_type": chat.get("extracted_message_type", ""),
            "candidates_from": chat.get("candidates_from", ""),
            "response_contains_TESTCASE_CODE": "[TESTCASE_CODE]" in raw and not _resp_eq_prompt,
            "response_contains_UNRESOLVED": "[UNRESOLVED]" in raw and not _resp_eq_prompt,
            "prompt_contains_UNRESOLVED": "[UNRESOLVED]" in prompt_for_api,
        }
        run["last_raw_response_preview"] = raw[:2000]
        run["last_raw_response_chars"] = len(raw)
        run["last_raw_has_testcase_code"] = "[TESTCASE_CODE]" in raw and not _resp_eq_prompt
        run["last_raw_has_missing_context"] = "[MISSING_CONTEXT]" in raw and not _resp_eq_prompt
        run["last_raw_has_unresolved"] = "[UNRESOLVED]" in raw and not _resp_eq_prompt

        if _resp_eq_prompt:
            # Response equals prompt — Graph returned the user message text as the "reply",
            # or the extraction layer already rejected it and returned empty with a flag.
            _pf_cids = list(batch.get("candidate_ids") or [])
            _pf_reason = "API response extraction returned prompt text, not assistant answer."
            run["status_message"] = f"API_RESPONSE_EXTRACTION_FAILED chunk {idx + 1}: response equals prompt"
            for _pf_cid in _pf_cids:
                _pf_diag = {
                    "prompt_chars": len(prompt_for_api),
                    "response_chars": len(raw),
                    "api_result_class": "API_RESPONSE_EXTRACTION_FAILED",
                    "issue_reason": _pf_reason,
                    "response_equals_prompt": True,
                    "extraction_failed": _extraction_failed,
                    "rejected_prompt_echo_count": chat.get("rejected_prompt_echo_count", 0),
                    "extracted_message_index": chat.get("extracted_message_index"),
                    "extracted_message_type": chat.get("extracted_message_type", ""),
                    "candidates_from": chat.get("candidates_from", ""),
                    "prompt_contains_UNRESOLVED": "[UNRESOLVED]" in prompt_for_api,
                }
                save_draft(gtest_state, draft_key=_pf_cid, draft={
                    "full_snippet": "",
                    "code_body": "",
                    "code_status": "NEEDS_REVIEW",
                    "workflow_message": "API_RESPONSE_EXTRACTION_FAILED: Graph returned prompt instead of assistant reply",
                    "is_fallback_scaffold": False,
                    "issue_reason": "api_response_equals_prompt",
                    "generation_source": "COPILOT_BATCH",
                    "api_diag": _pf_diag,
                    "api_prompt_preview": prompt_for_api[:500],
                    "api_raw_response_preview": "",
                    "unresolved_message": "API echoed the request prompt as its reply — not an UNRESOLVED result. Retry generation.",
                }, engineer_edited=False, wrap_markers=False)
            _pf_results = [
                {"candidate_id": c, "ok": False, "workflow_status": "NEEDS_REVIEW",
                 "code_status": "NEEDS_REVIEW", "issue_reason": "api_response_equals_prompt",
                 "full_snippet": "", "api_diag": {"api_result_class": "API_RESPONSE_EXTRACTION_FAILED"}}
                for c in _pf_cids
            ]
            for r in _pf_results:
                all_results.append(r)
            total_review += len(_pf_cids)
            run.update({"saved": total_saved, "needs_review": total_review, "error": total_error,
                        "batch_index": idx + 1, "completed_chunks": idx + 1,
                        "queued_chunks": max(len(prompts) - idx - 1, 0),
                        "status_message": f"API_RESPONSE_EXTRACTION_FAILED on chunk {idx + 1}: response echoed prompt."})
            if job_output:
                from pathlib import Path as _Path
                flush_batch_run_checkpoint(_Path(job_output), gtest_state)
            continue

        # Stash target rows so UNRESOLVED path can reference them
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
            _prompt_chars=len(prompt_for_api),
            _prompt_preview=prompt_for_api[:500],
            _raw_response_preview=raw[:500],
        )
        gtest_state.pop("_batch_target_rows", None)
        run["last_api_diag"] = one.get("api_diag") or {}
        # Enrich UNRESOLVED results: if prompt was complete, annotate draft with clear message
        _pd = run.get("last_prompt_diag") or {}
        _prompt_complete = (
            _pd.get("api_prompt_contains_relevant_rules")
            and _pd.get("api_prompt_contains_input_code")
            and _pd.get("api_prompt_contains_output_code")
            and _pd.get("api_prompt_contains_fixture")
        )
        _unresolved_message = (
            "Copilot API returned UNRESOLVED despite complete prompt. Try Web import or retry API."
            if _prompt_complete
            else "Copilot API returned UNRESOLVED — prompt may be missing context (rules/fixture/code samples)."
        )
        for _r in (one.get("results") or []):
            if (_r.get("api_diag") or {}).get("api_result_class") == "UNRESOLVED":
                _cid = str(_r.get("candidate_id") or "")
                _dr = (gtest_state.get("drafts") or {}).get(_cid)
                if _dr is not None:
                    _dr["prompt_complete"] = bool(_prompt_complete)
                    _dr["unresolved_message"] = _unresolved_message
                    if _prompt_complete:
                        _dr["issue_reason"] = "unresolved_despite_complete_prompt"
                    (_dr.setdefault("api_diag", {}))["prompt_complete"] = bool(_prompt_complete)
        chunk_results = list(one.get("results") or [])
        s = dict(one.get("summary") or {})
        run = gtest_state.setdefault("copilot_batch", {}).setdefault("run", {})

        # --- UNRESOLVED direct-code retry: fire when prompt was confirmed complete ---
        if _prompt_complete:
            _unres_cids = {
                str(_r.get("candidate_id") or "")
                for _r in chunk_results
                if (_r.get("api_diag") or {}).get("api_result_class") == "UNRESOLVED"
                and str(_r.get("candidate_id") or "")
            }
            if _unres_cids:
                # Run smoke test once per batch run to discover which API mode works.
                if not run.get("smoke_diag"):
                    run["status_message"] = "Running API smoke test before direct-code retry…"
                    run["smoke_diag"] = run_copilot_api_smoke_test(cfg, user_id=user_id)
                _smoke = run["smoke_diag"]
                # Use working mode from smoke (fall back to fresh if smoke itself failed)
                _retry_call_kwargs: dict[str, Any] = dict(
                    _smoke.get("working_mode_kwargs") or {"reuse_session_conversation": False, "persist_conversation": False}
                )
                _smoke_ok = bool(_smoke.get("smoke_ok"))
                _smoke_mode = str(_smoke.get("working_mode") or "unknown")

                run["status_message"] = (
                    f"Direct-code retry for {len(_unres_cids)} UNRESOLVED TC(s) "
                    f"(smoke={'OK:' + _smoke_mode if _smoke_ok else 'FAILED'})."
                )
                _retry_diags: dict[str, Any] = {}
                for _retry_row in (batch.get("_target_rows") or []):
                    _retry_cid = str(_retry_row.get("candidate_id") or "")
                    if _retry_cid not in _unres_cids:
                        continue
                    _retry_prompt = build_copilot_unresolved_retry_prompt(_retry_row, gtest_state)
                    _rdiag: dict[str, Any] = {
                        "retry_used": True,
                        "retry_prompt_chars": len(_retry_prompt),
                        "retry_result_class": "TIMEOUT",
                        "retry_response_preview": "",
                        "smoke_ok": _smoke_ok,
                        "smoke_mode": _smoke_mode,
                    }
                    _retry_chat = run_copilot_chat_result(
                        cfg, _retry_prompt,
                        user_id=user_id,
                        **_retry_call_kwargs,
                    )
                    if _retry_chat.get("ok"):
                        _retry_raw = str(_retry_chat.get("reply") or _retry_chat.get("content") or "")
                        _retry_resp_eq_prompt = bool(_retry_raw) and _retry_raw[:200] == _retry_prompt[:200]
                        _rdiag["retry_response_equals_prompt"] = _retry_resp_eq_prompt
                        _rdiag["retry_response_preview"] = _retry_raw[:500]
                        if _retry_resp_eq_prompt:
                            # Retry also returned prompt text — API_PARSE_FAIL, skip import
                            _rdiag["retry_result_class"] = "API_PARSE_FAIL"
                            _dr = (gtest_state.get("drafts") or {}).get(_retry_cid)
                            if _dr is not None:
                                _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_rdiag}
                                _dr["unresolved_message"] = "API echoed prompt as reply on retry. Use Web import."
                                _dr["issue_reason"] = "api_response_equals_prompt"
                            _retry_diags[_retry_cid] = _rdiag
                            continue
                        gtest_state["_batch_target_rows"] = [_retry_row]
                        _retry_one = apply_copilot_batch_import(
                            bundle, gtest_state, job_output,
                            content=_retry_raw,
                            expected_candidate_ids=[_retry_cid],
                            language=language,
                            generation_source="COPILOT_API_DIRECT_RETRY",
                            persist_errors=False,
                            _prompt_chars=len(_retry_prompt),
                            _prompt_preview=_retry_prompt[:500],
                            _raw_response_preview=_retry_raw[:500],
                        )
                        gtest_state.pop("_batch_target_rows", None)
                        _retry_res = next(
                            (r for r in (_retry_one.get("results") or []) if str(r.get("candidate_id") or "") == _retry_cid),
                            None,
                        )
                        if _retry_res:
                            _retry_class = (_retry_res.get("api_diag") or {}).get("api_result_class", "UNKNOWN")
                            _rdiag["retry_result_class"] = _retry_class
                            _dr = (gtest_state.get("drafts") or {}).get(_retry_cid)
                            if _retry_class not in ("UNRESOLVED", "MISSING_CONTEXT", "ERROR", "NOT_FOUND", "EMPTY", "NO_TEST_F", "TIMEOUT", "UNKNOWN"):
                                # Retry produced code — replace the UNRESOLVED result in chunk
                                _retry_res["generation_source"] = "COPILOT_API_DIRECT_RETRY"
                                for _ci, _cr in enumerate(chunk_results):
                                    if str(_cr.get("candidate_id") or "") == _retry_cid:
                                        chunk_results[_ci] = _retry_res
                                        break
                                if _retry_class == "SAVED":
                                    s["saved"] = int(s.get("saved") or 0) + 1
                                    s["needs_review"] = max(0, int(s.get("needs_review") or 0) - 1)
                                if _dr is not None:
                                    _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_rdiag}
                            else:
                                # Still UNRESOLVED/failed after direct-code retry
                                _smoke_summary = (
                                    f"Smoke={_smoke_mode}" if _smoke_ok else "Smoke=FAILED_ALL_VARIANTS"
                                )
                                if _dr is not None:
                                    _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_rdiag}
                                    _dr["unresolved_message"] = (
                                        "API cannot generate despite complete prompt. "
                                        "Use Web import or manual review."
                                    )
                                    _dr["issue_reason"] = "unresolved_despite_retry"
                                    _dr["smoke_summary"] = _smoke_summary
                        else:
                            _rdiag["retry_result_class"] = "NO_RESULT"
                    else:
                        # Retry API call failed
                        _rdiag["retry_result_class"] = "TIMEOUT" if str(_retry_chat.get("error_category") or "") == "m365_graph_timeout" else "ERROR"
                        _dr = (gtest_state.get("drafts") or {}).get(_retry_cid)
                        if _dr is not None:
                            _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_rdiag}
                    _retry_diags[_retry_cid] = _rdiag
                run["retry_diags"] = _retry_diags

        # --- Fixture-only MISSING_CONTEXT retry ---
        # When the first pass returned MISSING_CONTEXT only for fixture and the group
        # mapping already has the fixture, retry once with build_copilot_fixture_retry_prompt.
        # This handles Copilot ignoring EXACT GROUP CONTEXT on the first pass.
        _fmc_candidates = [
            _r for _r in chunk_results
            if ((_r.get("api_diag") or {}).get("api_result_class") == "MISSING_CONTEXT"
                and (_r.get("api_diag") or {}).get("fixture_suppressed_by_group_mapping")
                and str((_r.get("api_diag") or {}).get("resolved_group_fixture") or "")
                and not (_r.get("missing_context") or []))
        ]
        if _fmc_candidates:
            run["status_message"] = (
                f"Fixture-only MISSING_CONTEXT retry for {len(_fmc_candidates)} TC(s) "
                "(Copilot ignored EXACT GROUP CONTEXT on first pass)."
            )
            _fmc_retry_diags: dict[str, Any] = {}
            for _fmc_r in _fmc_candidates:
                _fmc_cid = str(_fmc_r.get("candidate_id") or "")
                _fmc_fixture = str((_fmc_r.get("api_diag") or {}).get("resolved_group_fixture") or "")
                if not _fmc_cid or not _fmc_fixture:
                    continue
                _fmc_row = next(
                    (r for r in (batch.get("_target_rows") or []) if str(r.get("candidate_id") or "") == _fmc_cid),
                    None,
                )
                if not _fmc_row:
                    continue
                _fmc_prompt = build_copilot_fixture_retry_prompt(_fmc_row, _fmc_fixture)
                _fmc_rdiag: dict[str, Any] = {
                    "fixture_retry_used": True,
                    "fixture_retry_fixture": _fmc_fixture,
                    "fixture_retry_prompt_chars": len(_fmc_prompt),
                    "fixture_retry_result_class": "TIMEOUT",
                    "fixture_retry_response_preview": "",
                    "prompt_contains_exact_fixture": True,
                    "prompt_contains_TryTo_xxx": False,
                }
                _fmc_chat = run_copilot_chat_result(
                    cfg, _fmc_prompt, user_id=user_id,
                    reuse_session_conversation=False, persist_conversation=False,
                )
                if _fmc_chat.get("ok"):
                    _fmc_raw = str(_fmc_chat.get("reply") or _fmc_chat.get("content") or "")
                    _fmc_rdiag["fixture_retry_response_preview"] = _fmc_raw[:500]
                    gtest_state["_batch_target_rows"] = [_fmc_row]
                    _fmc_one = apply_copilot_batch_import(
                        bundle, gtest_state, job_output,
                        content=_fmc_raw,
                        expected_candidate_ids=[_fmc_cid],
                        language=language,
                        generation_source="COPILOT_API_FIXTURE_RETRY",
                        persist_errors=False,
                        _prompt_chars=len(_fmc_prompt),
                        _prompt_preview=_fmc_prompt[:500],
                        _raw_response_preview=_fmc_raw[:500],
                    )
                    gtest_state.pop("_batch_target_rows", None)
                    _fmc_res = next(
                        (r for r in (_fmc_one.get("results") or []) if str(r.get("candidate_id") or "") == _fmc_cid),
                        None,
                    )
                    if _fmc_res:
                        _fmc_class = (_fmc_res.get("api_diag") or {}).get("api_result_class", "UNKNOWN")
                        _fmc_rdiag["fixture_retry_result_class"] = _fmc_class
                        _dr = (gtest_state.get("drafts") or {}).get(_fmc_cid)
                        if _fmc_class not in ("MISSING_CONTEXT", "UNRESOLVED", "ERROR", "NOT_FOUND", "EMPTY", "NO_TEST_F", "TIMEOUT", "UNKNOWN"):
                            # Retry produced code — replace the MISSING_CONTEXT result
                            _fmc_res["generation_source"] = "COPILOT_API_FIXTURE_RETRY"
                            for _ci, _cr in enumerate(chunk_results):
                                if str(_cr.get("candidate_id") or "") == _fmc_cid:
                                    chunk_results[_ci] = _fmc_res
                                    break
                            if _fmc_class == "SAVED":
                                s["saved"] = int(s.get("saved") or 0) + 1
                                s["needs_review"] = max(0, int(s.get("needs_review") or 0) - 1)
                            if _dr is not None:
                                _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_fmc_rdiag}
                        else:
                            # Copilot still ignored fixture after explicit retry prompt
                            _fmc_rdiag["fixture_retry_result_class"] = _fmc_class
                            if _dr is not None:
                                _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_fmc_rdiag}
                                _dr["issue_reason"] = "fixture_context_ignored_by_copilot"
                                _dr["fixture_ignored_diagnostics"] = {
                                    "resolved_group_id": str((_fmc_r.get("api_diag") or {}).get("resolved_group_id") or ""),
                                    "resolved_group_fixture": _fmc_fixture,
                                    "prompt_contains_exact_fixture": True,
                                    "prompt_contains_TryTo_xxx": False,
                                    "raw_missing_context": _fmc_raw[:500],
                                }
                else:
                    # Retry API call failed
                    _fmc_rdiag["fixture_retry_result_class"] = (
                        "TIMEOUT" if str(_fmc_chat.get("error_category") or "") == "m365_graph_timeout" else "ERROR"
                    )
                    _dr = (gtest_state.get("drafts") or {}).get(_fmc_cid)
                    if _dr is not None:
                        _dr["api_diag"] = {**(_dr.get("api_diag") or {}), **_fmc_rdiag}
                _fmc_retry_diags[_fmc_cid] = _fmc_rdiag
            run["fixture_retry_diags"] = _fmc_retry_diags

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
            # Persist each ERROR candidate as metadata-only failure — no scaffold code
            for r in chunk_results:
                if str(r.get("workflow_status") or r.get("code_status") or "").upper() == "ERROR":
                    _cid = str(r.get("candidate_id") or "")
                    if _cid:
                        _persist_api_failure(
                            gtest_state,
                            candidate_id=_cid,
                            error_message=str(r.get("workflow_message") or reason),
                            api_result_class="API_PARSE_ERROR",
                            issue_reason="api_parse_error",
                        )
                        r["fallback_prompt"] = prompt_for_web_fallback
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
