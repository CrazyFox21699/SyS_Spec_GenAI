"""M365 Copilot — generate GTest code from Code Context Pack."""

from __future__ import annotations

import json
import re
from typing import Any

from web.code_style_samples import validate_copilot_code_draft, validate_gtest_code_for_save
from web.m365_copilot import run_copilot_chat_result

_CPP_FENCE_RE = re.compile(r"```(?:cpp|c\+\+)?\s*\n?([\s\S]*?)```", re.IGNORECASE)
_ASSUMPTIONS_RE = re.compile(r"(?:^|\n)\s*ASSUMPTIONS?\s*:\s*\n([\s\S]*)$", re.IGNORECASE)
_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _finalize_copilot_code_result(
    parsed: dict[str, Any],
    validation: dict[str, Any],
    raw: str,
    *,
    provider: str,
) -> dict[str, Any]:
    """Return draft whenever Copilot produced code; validation is advisory until Save."""
    has_code = bool(parsed.get("full_snippet") or parsed.get("code_body"))
    if not has_code:
        return {
            "ok": False,
            "draft": parsed,
            "validation": validation,
            "error": "Copilot returned no C++ code block.",
            "error_category": "parse_failed",
            "raw_preview": raw[:800],
            "provider": provider,
        }
    flags = list(validation.get("flags") or [])
    warnings = list(validation.get("warnings") or [])
    review_note = None
    if flags and not validation.get("ok"):
        review_note = f"Review before Save: {', '.join(flags)}"
    elif warnings:
        review_note = f"Warnings: {'; '.join(warnings[:3])}"
    return {
        "ok": True,
        "draft": parsed,
        "validation": validation,
        "error": review_note,
        "error_category": "validation_review" if review_note else None,
        "raw_preview": raw[:800],
        "provider": provider,
    }


def _parse_json_response(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def _format_style_samples(style_ref: dict[str, Any], *, slim: bool = False) -> str:
    samples = style_ref.get("samples") or []
    if not samples:
        return "[]"
    primary = style_ref.get("primary_reference") or {}
    lines = [
        "Use reference tests for FIXTURE class, helper calls (RunForMs, Evaluate…), "
        "comment style, and assertion patterns ONLY.",
        "Do NOT copy signal values or testcase logic from references — use expected_input/output below.",
    ]
    if primary.get("test_name"):
        lines.append(f"Primary style anchor: {primary.get('test_name')} ({primary.get('source_file') or ''})")
    blocks: list[dict[str, str]] = []
    limit = 1 if slim else 3
    snippet_cap = 2000 if slim else 8000
    for row in samples[:limit]:
        blocks.append(
            {
                "label": str(row.get("label") or row.get("test_name") or "ref"),
                "fixture": str(row.get("fixture_class") or ""),
                "snippet": str(row.get("snippet") or "")[:snippet_cap],
            }
        )
    style_cap = 4000 if slim else 12000
    return ("\n".join(lines) + "\n\n" + json.dumps(blocks, ensure_ascii=False, indent=2))[:style_cap]


_GTEST_OUTPUT_RULES = (
    "Output format (mandatory):\n"
    "- Return ONE ```cpp code block containing the complete GTest (spec comments + TEST/TEST_F).\n"
    "- After the code block, add a short section starting with ASSUMPTIONS: (bullet list, max 5 lines).\n"
    "- Do NOT wrap output in JSON. Do NOT add markdown outside the cpp fence except ASSUMPTIONS.\n\n"
    "Coding rules (mandatory):\n"
    "- Generate GTest C++ ONLY (TEST or TEST_F).\n"
    "- Follow the loaded .cpp sample for fixture class, helpers, and comment style.\n"
    "- Do NOT invent APIs, helpers, or macros not shown in the sample snippet.\n"
    "- Include candidate_id in the spec comment block (e.g. // TC_PM_004 …).\n"
    "- Map Given:/When: lines from expected_input; Then: lines from expected_output.\n"
    "- Assert observable outputs only — no hidden/internal state unless the spec states it.\n"
    "- No TODO, no placeholder comments, no pseudo-code.\n"
)


def parse_copilot_cpp_response(text: str) -> dict[str, Any]:
    """Extract GTest C++ from Copilot paste (fenced block or raw TEST_F body)."""
    raw = str(text or "").strip()
    if not raw:
        return {"full_snippet": "", "code_body": "", "assumptions": [], "open_questions": []}

    assumptions: list[str] = []
    body = raw
    m_assume = _ASSUMPTIONS_RE.search(raw)
    if m_assume:
        body = raw[: m_assume.start()].strip()
        for line in m_assume.group(1).splitlines():
            line = re.sub(r"^[\s\-*•]+", "", line.strip())
            if line:
                assumptions.append(line)

    fence = _CPP_FENCE_RE.search(body)
    if fence:
        code = fence.group(1).strip()
    else:
        code = body.strip()
        code = re.sub(r"^```(?:cpp|c\+\+)?\s*", "", code, flags=re.IGNORECASE)
        code = re.sub(r"\s*```$", "", code).strip()

    if not code:
        return {"full_snippet": "", "code_body": "", "assumptions": assumptions, "open_questions": []}

    body_start = code.find("TEST_F(")
    if body_start < 0:
        body_start = code.find("TEST(")
    if body_start > 0:
        spec = code[:body_start].strip()
        test_body = code[body_start:].strip()
    elif body_start == 0:
        spec, test_body = "", code
    else:
        spec, test_body = "", code

    full = "\n".join(part for part in (spec, test_body) if part)
    return {
        "spec_comment_block": spec,
        "code_body": test_body,
        "full_snippet": full,
        "assumptions": assumptions,
        "open_questions": [],
    }


def _resolve_copilot_draft(raw: str) -> dict[str, Any]:
    stripped = str(raw or "").strip()
    if stripped.startswith("{"):
        js = _parse_json_response(raw)
        if js.get("full_snippet") or js.get("code_body"):
            return js
    parsed = parse_copilot_cpp_response(raw)
    if parsed.get("full_snippet") or parsed.get("code_body"):
        return parsed
    return _parse_json_response(raw)


def build_gtest_copilot_prompt(
    context_pack: dict[str, Any],
    *,
    code_rule: str = "",
    existing_code: str = "",
    slim: bool = False,
) -> str:
    """Full prompt for Copy Prompt / M365 — testcase → GTest workbench."""
    tc = context_pack.get("testcase") or {}
    harness = context_pack.get("harness") or {}
    io_map = context_pack.get("io_variable_map") or {}
    logic = context_pack.get("logic") or {}
    style_ref = context_pack.get("code_style_reference") or {}
    style_text = _format_style_samples(style_ref, slim=slim)
    cid = str(tc.get("candidate_id") or tc.get("id") or "")

    refine_block = ""
    code = str(existing_code or "").strip()
    if code:
        refine_block = (
            "Current editor code (apply Code Rule / Change Request to this snippet):\n"
            f"```cpp\n{code[:14000]}\n```\n\n"
        )

    rule = str(code_rule or "").strip()
    rule_block = f"Code Rule / Change Request:\n{rule[:3000]}\n\n" if rule else ""

    return (
        "You are Microsoft 365 Copilot writing Google Test (GTest) C++ for automotive ALEX.\n"
        "This is a testcase → code generation workbench. Write production-ready GTest for ONE testcase.\n\n"
        f"{_GTEST_OUTPUT_RULES}"
        f"{rule_block}"
        f"{refine_block}"
        f"Project reference GTest (.cpp sample — STYLE ONLY, do not copy signal values):\n{style_text}\n\n"
        f"Harness:\n{json.dumps(harness, ensure_ascii=False)[:2000]}\n\n"
        f"io_variable_map:\n{json.dumps(io_map, ensure_ascii=False)[:3000]}\n\n"
        f"Logic (context):\n{json.dumps(logic, ensure_ascii=False)[:2000]}\n\n"
        f"Testcase (candidate_id={cid}):\n{json.dumps(tc, ensure_ascii=False)[:6000]}\n\n"
        "Remember: spec comment must include candidate_id; map Given/When/Then from testcase I/O; "
        "follow sample .cpp style; return ```cpp block + ASSUMPTIONS only."
    )


def build_gtest_copilot_prompt_followup(
    context_pack: dict[str, Any],
    *,
    code_rule: str = "",
) -> str:
    """Short prompt for the next testcase in the same Copilot web chat."""
    tc = context_pack.get("testcase") or {}
    cid = str(tc.get("candidate_id") or tc.get("id") or "")
    inp = str(tc.get("expected_input") or "").strip()
    out = str(tc.get("expected_output") or "").strip()
    rule = str(code_rule or "").strip()
    rule_block = f"Change request:\n{rule[:1500]}\n\n" if rule else ""
    return (
        "Continue in the Same GTest style as your previous answer in THIS chat.\n"
        f"Write ONE new TEST_F for candidate_id {cid}.\n\n"
        f"Expected input:\n{inp[:4000]}\n\n"
        f"Expected output:\n{out[:4000]}\n\n"
        f"{rule_block}"
        f"{_GTEST_OUTPUT_RULES}"
        f"Spec comment must include // {cid}. Return ```cpp block + ASSUMPTIONS only."
    )


def build_gtest_context_summary(context_pack: dict[str, Any], *, code_rule: str = "", sample_label: str = "") -> dict[str, Any]:
    tc = context_pack.get("testcase") or {}
    style_ref = context_pack.get("code_style_reference") or {}
    samples = style_ref.get("samples") or []
    first = samples[0] if samples else {}
    return {
        "candidate_id": str(tc.get("candidate_id") or tc.get("id") or ""),
        "test_function": str(tc.get("test_function") or ""),
        "expected_input": str(tc.get("expected_input") or ""),
        "expected_output": str(tc.get("expected_output") or ""),
        "code_rule": str(code_rule or "").strip(),
        "sample_loaded": bool(samples),
        "sample_label": sample_label or str(first.get("label") or first.get("source_file") or ""),
        "fixture_class": str((style_ref.get("primary_reference") or {}).get("fixture_class") or first.get("fixture_class") or ""),
    }


def _writer_prompt(
    context_pack: dict[str, Any],
    *,
    engineer_note: str = "",
    copilot_prompt_override: str = "",
    slim: bool = False,
) -> str:
    tc = context_pack.get("testcase") or {}
    harness = context_pack.get("harness") or {}
    baseline = context_pack.get("baseline_skeleton") or {}
    patterns = context_pack.get("verification_patterns") or []
    siblings = context_pack.get("sibling_assertions") or []
    io_map = context_pack.get("io_variable_map") or {}
    logic = context_pack.get("logic") or {}
    style_ref = context_pack.get("code_style_reference") or {}
    style_text = _format_style_samples(style_ref, slim=slim)

    sibling_block = ""
    if not slim and siblings:
        sibling_block = f"Sibling assertions (same Given):\n{json.dumps(siblings, ensure_ascii=False)[:1500]}\n\n"

    pattern_block = ""
    if patterns:
        pat_cap = 800 if slim else 2000
        pattern_block = f"Verification patterns:\n{json.dumps(patterns, ensure_ascii=False)[:pat_cap]}\n\n"

    baseline_block = ""
    if baseline and not slim:
        baseline_block = (
            "Python baseline skeleton (structure reference, improve with project style):\n"
            f"{json.dumps({k: baseline.get(k) for k in ('test_name', 'code_body', 'full_snippet') if baseline.get(k)}, ensure_ascii=False)[:4000]}\n\n"
        )
    elif baseline and slim and baseline.get("test_name"):
        baseline_block = f"Baseline test_name hint: {baseline.get('test_name')}\n\n"

    combined_rule = "\n".join(
        part for part in (engineer_note.strip(), copilot_prompt_override.strip()) if part
    )
    pack = dict(context_pack)
    if pattern_block or sibling_block or baseline_block:
        pack = {
            **context_pack,
            "_extra_patterns": pattern_block + sibling_block + baseline_block,
        }
    base = build_gtest_copilot_prompt(pack, code_rule=combined_rule, slim=slim)
    extra = pattern_block + sibling_block + baseline_block
    if extra:
        return base + "\nAdditional context:\n" + extra
    return base


def run_code_write(
    context_pack: dict[str, Any],
    cfg: dict[str, Any],
    *,
    engineer_note: str = "",
    copilot_prompt_override: str = "",
    reuse_conversation: bool = False,
    slim: bool = False,
) -> dict[str, Any]:
    prompt = _writer_prompt(
        context_pack,
        engineer_note=engineer_note,
        copilot_prompt_override=copilot_prompt_override,
        slim=slim,
    )
    chat = run_copilot_chat_result(
        cfg,
        prompt,
        reuse_session_conversation=reuse_conversation,
    )
    if not chat.get("ok"):
        return {
            "ok": False,
            "error": chat.get("error") or "M365 Copilot request failed",
            "error_category": chat.get("error_category") or "m365_copilot_api",
            "graph_status": chat.get("graph_status"),
            "raw_preview": chat.get("raw_preview") or "",
            "user_action": chat.get("user_action"),
            "provider": "m365_copilot",
        }
    raw = str(chat.get("reply") or "")
    parsed = _resolve_copilot_draft(raw)
    if not parsed.get("full_snippet") and parsed.get("code_body"):
        comments = str(parsed.get("spec_comment_block") or "").strip()
        body = str(parsed.get("code_body") or "").strip()
        parsed["full_snippet"] = "\n".join(x for x in (comments, body) if x)
    tc = context_pack.get("testcase") or {}
    cid = str(tc.get("candidate_id") or tc.get("id") or "")
    sample_snippet = str(((context_pack.get("code_style_reference") or {}).get("samples") or [{}])[0].get("snippet") or "")
    validation = validate_gtest_code_for_save(
        parsed.get("full_snippet") or parsed.get("code_body") or "",
        candidate_id=cid,
        sample_snippet=sample_snippet,
    )
    return _finalize_copilot_code_result(parsed, validation, raw, provider="m365_copilot")


def run_code_refine(
    existing_code: str,
    instruction: str,
    cfg: dict[str, Any],
    *,
    test_name: str = "",
    context_pack: dict[str, Any] | None = None,
    reuse_conversation: bool = False,
) -> dict[str, Any]:
    """Copilot edit with optional testcase/harness context — handles open-ended engineer feedback."""
    code = str(existing_code or "").strip()
    note = str(instruction or "").strip()
    if not code or not note:
        return {
            "ok": False,
            "error": "existing_code and instruction are required",
            "error_category": "validation",
            "provider": "m365_copilot",
        }
    context_block = ""
    if context_pack:
        prompt = build_gtest_copilot_prompt(context_pack, code_rule=note, existing_code=code, slim=True)
    else:
        prompt = (
            "You are Microsoft 365 Copilot editing Google Test (GTest) C++ in ALEX.\n"
            f"{_GTEST_OUTPUT_RULES}"
            f"Code Rule / Change Request:\n{note[:3000]}\n\n"
            f"Current code:\n```cpp\n{code[:14000]}\n```\n"
        )
    chat = run_copilot_chat_result(
        cfg,
        prompt,
        reuse_session_conversation=reuse_conversation,
    )
    if not chat.get("ok"):
        return {
            "ok": False,
            "error": chat.get("error") or "M365 Copilot request failed",
            "error_category": chat.get("error_category") or "m365_copilot_api",
            "graph_status": chat.get("graph_status"),
            "raw_preview": chat.get("raw_preview") or "",
            "user_action": chat.get("user_action"),
            "provider": "m365_copilot",
        }
    raw = str(chat.get("reply") or "")
    parsed = _resolve_copilot_draft(raw)
    if not parsed.get("full_snippet") and parsed.get("code_body"):
        comments = str(parsed.get("spec_comment_block") or "").strip()
        body = str(parsed.get("code_body") or "").strip()
        parsed["full_snippet"] = "\n".join(x for x in (comments, body) if x)
    sample_snippet = ""
    if context_pack:
        sample_snippet = str(((context_pack.get("code_style_reference") or {}).get("samples") or [{}])[0].get("snippet") or "")
    validation = validate_gtest_code_for_save(
        parsed.get("full_snippet") or parsed.get("code_body") or "",
        candidate_id=test_name,
        sample_snippet=sample_snippet,
    )
    return _finalize_copilot_code_result(parsed, validation, raw, provider="m365_copilot_refine")


def code_write_batch_size(cfg: dict[str, Any] | None) -> int:
    if not cfg:
        return 3
    assist = cfg.get("assist") or {}
    return max(1, min(8, int(assist.get("copilot_code_batch_size", assist.get("copilot_write_batch_size", 3)))))


# ─── Post-generation comment normalizer ───────────────────────────────────────

_BC_RE = re.compile(r"/\*\*?[\s\S]*?\*/")

_BC_FIELD_KEYS = ("testcase_id", "test group", "event", "test design", "given", "when", "then")

# When text is "executable" only when it explicitly names igsw_Main_Run or a main-call trigger.
# Passive conditions like "PWR_STATE = ON" or "evaluate X" are NOT executable.
_EXECUTABLE_WHEN_RE = re.compile(r"\bigsw_Main_Run\b|\bmain\s+(?:call|function)\b", re.I)

_PLACEHOLDER_FIXTURE_RE = re.compile(r"^TryTo[A-Za-z0-9_]+$")
_TESTF_FIXTURE_RE = re.compile(r"\bTEST_F\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)")


def extract_testf_fixture_name(code: str) -> str:
    """Return the fixture class name from the first TEST_F(...) in code, or ''."""
    m = _TESTF_FIXTURE_RE.search(str(code or ""))
    return m.group(1) if m else ""


def replace_testf_fixture(code: str, new_fixture: str) -> str:
    """Replace the fixture class in all TEST_F(OldFixture, ...) with new_fixture."""
    return re.sub(
        r"(\bTEST_F\s*\(\s*)[A-Za-z_][A-Za-z0-9_]*",
        lambda m: m.group(1) + new_fixture,
        str(code or ""),
    )


def is_placeholder_testf_fixture(fixture: str, group_fixture: str = "") -> bool:
    """Return True when fixture looks like an auto-generated TryTo placeholder.

    A TryTo-prefixed name that matches the real group fixture is NOT a placeholder.
    """
    if not fixture:
        return False
    if not _PLACEHOLDER_FIXTURE_RE.match(fixture):
        return False
    return fixture != group_fixture if group_fixture else True


def _parse_block_comment_fields(block: str) -> dict[str, str]:
    """Extract key→value pairs from a /* … */ block comment.

    Handles both compact (``* key: value``) and verbose bullet formats.
    """
    inner = re.sub(r"^\s*/\*+\s*", "", block).rstrip()
    inner = re.sub(r"\s*\*+/\s*$", "", inner)
    lines = [re.sub(r"^\s*\*\s?", "", ln) for ln in inner.splitlines()]

    fields: dict[str, str] = {}
    cur_key: str | None = None
    cur_parts: list[str] = []

    def _flush() -> None:
        if cur_key:
            fields[cur_key] = _squash_bullets(cur_parts)

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        matched_kw = None
        for kw in _BC_FIELD_KEYS:
            if stripped.lower().startswith(kw + ":"):
                matched_kw = kw
                break
        if matched_kw:
            _flush()
            cur_key = matched_kw.lower().replace(" ", "_")
            val = stripped[len(matched_kw) + 1 :].strip()
            cur_parts = [val] if val else []
        elif cur_key:
            cur_parts.append(stripped)
        elif not fields.get("testcase_id") and re.match(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$", stripped):
            # Bare testcase ID on first line in new comment format (no "testcase_id:" label).
            fields["testcase_id"] = stripped

    _flush()
    return fields


def _squash_bullets(lines: list[str]) -> str:
    """Join bullet-list lines into one semicolon-separated string."""
    parts = []
    for ln in lines:
        ln = re.sub(r"^[-•*]\s+", "", ln.strip())
        if ln:
            parts.append(ln)
    return "; ".join(parts)


def _extract_given_when(text: str) -> tuple[str, str]:
    """Return (given_text, when_text) from an expected_input string."""
    given: list[str] = []
    when: list[str] = []
    mode = "given"
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^(?:When|Action)\s*:", s, re.I):
            mode = "when"
            val = re.sub(r"^[^:]+:\s*", "", s).strip()
            if val:
                when.append(val)
        elif re.match(r"^Given\s*:", s, re.I):
            mode = "given"
            val = re.sub(r"^Given\s*:\s*", "", s, flags=re.I).strip()
            # Split inline ". When: <text>" embedded within the Given value.
            # E.g. "WMODE_CMD = 1. When: PWR_STATE = ON" → given="WMODE_CMD = 1", when="PWR_STATE = ON"
            _when_m = re.search(r"\.\s*When\s*:\s*(.+)$", val, re.I)
            if _when_m:
                _when_part = _when_m.group(1).strip()
                val = val[: _when_m.start()].strip()
                if _when_part:
                    when.append(_when_part)
            if val:
                given.append(val)
        elif mode == "given":
            given.append(s)
        else:
            when.append(s)
    return "; ".join(p for p in given if p)[:200], "; ".join(p for p in when if p)[:200]


def _extract_then(text: str) -> str:
    """Return condensed then text from an expected_output string."""
    parts = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^Then\s*:\s*", "", s, flags=re.I).strip()
        s = re.sub(r"^[-•*]\s*", "", s).strip()
        if s:
            parts.append(s)
    return "; ".join(parts)[:200]


def _compact_block_comment(fields: dict[str, str]) -> str:
    """Build a compact ``/* … */`` block comment from a fields dict.

    Format:
        /*
         * TC_IMP_007
         * Power will be reset to off
         * Power is ON and the accident happened make it to reset
         * Given: WMODE_CMD = 1
         * When: PWR_STATE = ON
         * Then: PWR_STATE = 1
         */

    Test Group and Event are emitted as plain values (no labels).
    If Event is identical to Test Group or blank, the Event line is omitted.
    No ``testcase_id:`` label, no ``Test design:`` line.
    """
    lines = ["/*"]
    cid = str(fields.get("testcase_id") or "").strip()
    if cid:
        lines.append(f" * {cid}")
    tg = str(fields.get("test_group") or "").strip()
    ev = str(fields.get("event") or "").strip()
    if tg:
        lines.append(f" * {tg}")
    if ev and ev != tg:
        lines.append(f" * {ev}")
    for key in ("given", "when", "then"):
        val = str(fields.get(key) or "").strip()
        if val:
            lines.append(f" * {key.capitalize()}: {val}")
    lines.append(" */")
    return "\n".join(lines)


def _check_cpp_statement_complete(
    lines: list[str], start: int, *, max_lookahead: int = 12
) -> tuple[bool, int]:
    """Return (is_complete, end_idx) for a C++ statement starting at lines[start].

    A statement is complete when all parentheses are balanced AND the combined
    uncommented text ends with a semicolon.  end_idx is one past the last line
    consumed (start+1 when incomplete, so only the initiating line is removed).
    """
    depth = 0
    for j in range(start, min(start + max_lookahead, len(lines))):
        uncommented = re.sub(r"//[^\n]*", "", lines[j].rstrip("\n"))
        for ch in uncommented:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        if depth == 0 and uncommented.rstrip().endswith(";"):
            return True, j + 1
    return False, start + 1


def sanitize_generated_cpp_body(
    body: str,
    *,
    has_explicit_when: bool = False,
    mapped_output_signals: frozenset[str] | None = None,
) -> str:
    """Sanitize a TEST_F inner body for syntax and policy safety after generation.

    Applied to ``body[head_end:]`` (everything after the opening ``{``).

    ``mapped_output_signals`` — upper-case signal names that have explicit
    condition/code entries in project memory.  Rule 5 is skipped for these
    signals so a memory-mapped ``EXPECT_THAT(PWR_STATE, Eq(1u))`` is never
    replaced with an ALEX_REVIEW comment.

    Rules applied in order per line:

    1. **Markdown bullets** — lines starting with ``- `` (not ``//``) are
       converted to ``// comment``.  Bullets referencing ``igsw_Main_Run``
       are removed entirely when ``has_explicit_when`` is False.
    2. **Bare igsw_Main_Run() call** — removed when ``has_explicit_when``
       is False.  The regex-based ``// When:`` replacement in
       ``normalize_testf_snippet`` handles the common ``// When:\\nigsw_Main_Run()``
       pattern; this rule catches any remaining standalone calls.
    3. **Incomplete EXPECT_CALL / EXPECT_THAT** — blocks whose parentheses
       are not balanced within 12 look-ahead lines are removed and replaced
       with ``// ALEX_REVIEW: <mapping> (incomplete ... removed)``.
    4. **Orphaned chained calls** (``.WillRepeatedly``, ``.WillOnce``, ``DoAll``)
       that appear without a preceding complete EXPECT_CALL in the output
       are removed (they are continuations of an already-removed incomplete block).
    5. **Raw ALL_CAPS signal in EXPECT_THAT** — replaced with ALEX_REVIEW
       *unless* the signal is listed in ``mapped_output_signals``.
    """
    _mapped = mapped_output_signals or frozenset()
    lines = body.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        lstripped = raw.lstrip()
        content = lstripped.rstrip("\n").rstrip()
        indent = raw[: len(raw) - len(lstripped)]

        # Rule 1: markdown bullet inside C++ body
        if content.startswith("- ") and not content.startswith("//"):
            bullet_text = content[2:].strip()
            if not has_explicit_when and re.search(r"\bigsw_Main_Run\b", bullet_text):
                i += 1
                continue
            out.append(f"{indent}// {bullet_text}\n")
            i += 1
            continue

        # Rule 2: bare igsw_Main_Run() call without explicit When
        if not has_explicit_when and not content.startswith("//"):
            if re.match(r"igsw_Main_Run\s*\(", content):
                i += 1
                continue

        # Rule 7: // When: igsw_Main_Run() comment without testspec executable authorization.
        # Copilot may generate // When: igsw_Main_Run() from style examples or project memory.
        # If testspec has no executable When, replace with the policy placeholder.
        if not has_explicit_when and re.match(r"//\s*When\s*:\s*", content, re.I):
            _when_val = re.sub(r"//\s*When\s*:\s*", "", content, flags=re.I).strip()
            if _when_val and _EXECUTABLE_WHEN_RE.search(_when_val):
                out.append(f"{indent}// When: no explicit action in testspec\n")
                i += 1
                continue

        # Rule 3: incomplete EXPECT_CALL / EXPECT_THAT block
        # Rule 5: syntactically complete EXPECT_THAT whose first argument is a raw ALL_CAPS
        #         signal identifier — these are read directly without an RTE accessor, which
        #         is invalid; replace with an ALEX_REVIEW so the engineer adds the accessor.
        expect_m = re.match(r"(EXPECT_CALL|EXPECT_THAT)\s*\(", content)
        if expect_m and not content.startswith("//"):
            is_complete, end_i = _check_cpp_statement_complete(lines, i)
            kind = expect_m.group(1)
            if is_complete:
                if kind == "EXPECT_THAT":
                    raw_sig_m = re.match(r"EXPECT_THAT\s*\(\s*([A-Z][A-Z0-9_]+)\s*,", content)
                    if raw_sig_m:
                        signal = raw_sig_m.group(1)
                        # Rule 5: skip replacement when signal has an explicit condition/code
                        # entry in project memory — the EXPECT_THAT is memory-authorised.
                        if signal in _mapped:
                            out.extend(lines[i:end_i])
                            i = end_i
                            continue
                        out.append(
                            f"{indent}// ALEX_REVIEW: output mapping missing for {signal}"
                            f" (raw signal in EXPECT_THAT — add RTE accessor to project memory)\n"
                        )
                        i = end_i
                        continue
                out.extend(lines[i:end_i])
                i = end_i
            else:
                sig_m = re.search(
                    r"EXPECT_CALL\s*\(\s*\w+\s*,\s*(\w+)|EXPECT_THAT\s*\(\s*(\w+)",
                    content,
                )
                signal = "unknown"
                if sig_m:
                    signal = sig_m.group(1) or sig_m.group(2) or "unknown"
                if kind == "EXPECT_CALL":
                    msg = f"input mapping missing for {signal} (incomplete EXPECT_CALL removed)"
                else:
                    msg = f"output mapping incomplete for {signal} (incomplete EXPECT_THAT removed)"
                out.append(f"{indent}// ALEX_REVIEW: {msg}\n")
                i = end_i
            continue

        # Rule 4: orphaned chained call without preceding EXPECT_CALL in output.
        # Only keep if the immediately preceding output line is a real (non-comment)
        # EXPECT_CALL line; ALEX_REVIEW comments mention EXPECT_CALL in their text
        # and must not be mistaken for a real call.
        if re.match(r"\.(WillRepeatedly|WillOnce|DoAll)\s*\(", content) and not content.startswith("//"):
            last_out = (out[-1] if out else "").strip()
            is_real_expect_call = (
                not last_out.startswith("//") and re.search(r"\bEXPECT_CALL\b", last_out) is not None
            )
            if not is_real_expect_call:
                i += 1
                continue

        out.append(raw)
        i += 1

    return "".join(out)


def _fill_section_labels(code: str, given: str, when: str, then: str) -> str:
    """Replace empty ``// Given:``, ``// When:``, ``// Then:`` lines with actual text."""
    vals: dict[str, str] = {"Given": given, "When": when, "Then": then}

    def _rep(m: re.Match) -> str:  # type: ignore[type-arg]
        indent = m.group(1)
        label = m.group(2)
        val = vals.get(label, "")
        return f"{indent}// {label}: {val}" if val else m.group(0)

    return re.compile(r"([ \t]*)//\s*(Given|When|Then)\s*:\s*$", re.MULTILINE).sub(_rep, code)


def normalize_testf_snippet(
    snippet: str,
    row: dict[str, Any] | None = None,
    *,
    memory_content: str = "",
) -> str:
    """Normalize comment style in a generated TEST_F snippet.

    - If a design block comment (containing testcase_id/event/Given/When/Then)
      is found inside the TEST_F body, move it to before TEST_F.
    - Reformat any such block comment to compact single-line-per-field style.
    - Fill empty ``// Given:``, ``// When:``, ``// Then:`` section labels using
      field values from the block comment or from the row metadata fallback.
    - Code body (EXPECT_CALL, igsw_Main_Run, EXPECT_THAT) is not modified.
    - ``@alex:begin`` / ``@alex:spec_hash`` lines (if already present) are
      preserved above the block comment.
    - ``memory_content`` — raw project memory markdown.  When provided, output
      signals with an explicit condition/code entry are preserved through the
      sanitizer (Rule 5 is skipped for those signals).

    Returns the snippet unchanged when there is nothing to normalize.
    """
    row = row or {}
    if not snippet:
        return snippet

    # Compute which output signals are memory-mapped (exempt from sanitizer Rule 5).
    _mapped_out_sigs: frozenset[str] = frozenset()
    if memory_content:
        from web.project_testcode_memory import get_mapped_output_signals
        _row_eo_for_map = str(row.get("expected_output") or "").strip()
        if _row_eo_for_map:
            _mapped_out_sigs = get_mapped_output_signals(memory_content, _row_eo_for_map)

    testf_m = re.search(r"\bTEST_?F?\s*\(", snippet)
    if not testf_m:
        return snippet

    testf_start = testf_m.start()
    pre = snippet[:testf_start]
    body = snippet[testf_start:]

    brace_m = re.search(r"\{", body)
    if not brace_m:
        return snippet
    head_end = brace_m.end()

    # Scan for a design block comment INSIDE the body (after the opening {)
    inner_text = body[head_end:]
    inner_bc_m = _BC_RE.search(inner_text)
    inner_bc = ""
    fields: dict[str, str] = {}
    if inner_bc_m:
        candidate = inner_bc_m.group(0)
        f = _parse_block_comment_fields(candidate)
        if f.get("testcase_id") or f.get("given") or f.get("event"):
            inner_bc = candidate
            fields = f

    # Also check for an existing block comment BEFORE TEST_F
    pre_bc_m = _BC_RE.search(pre)
    pre_bc = ""
    if pre_bc_m:
        pre_bc = pre_bc_m.group(0)
        if not fields:
            f2 = _parse_block_comment_fields(pre_bc)
            if f2.get("testcase_id") or f2.get("given"):
                fields = f2

    # No design block comment found — still apply body sanitizer for policy safety.
    if not inner_bc and not pre_bc:
        _row_ei0 = str(row.get("expected_input") or "").strip()
        _has_exec_when0 = False
        if _row_ei0:
            _, _rw0 = _extract_given_when(_row_ei0)
            _has_exec_when0 = bool(_rw0) and bool(_EXECUTABLE_WHEN_RE.search(_rw0))
        sanitized_inner = sanitize_generated_cpp_body(
            body[head_end:],
            has_explicit_when=_has_exec_when0,
            mapped_output_signals=_mapped_out_sigs,
        )
        if sanitized_inner != body[head_end:]:
            return pre + body[:head_end] + sanitized_inner
        return snippet

    # Rebuild fields from row metadata — row spec is authoritative when available.
    # This prevents malformed Copilot comments (e.g. event containing "Test design / purpose:")
    # from corrupting the final block comment.
    # Operation is NAMESPACE METADATA ONLY — never used as When.
    _row_cid = str(row.get("candidate_id") or row.get("id") or "").strip()
    _row_event = str(row.get("event") or row.get("test_function") or "").strip()
    _row_test_group = str(row.get("test_group") or "").strip()
    _row_ei = str(row.get("expected_input") or "").strip()
    _row_eo = str(row.get("expected_output") or "").strip()

    if _row_cid:
        fields["testcase_id"] = _row_cid
    if _row_test_group:
        fields["test_group"] = _row_test_group
    if _row_event:
        fields["event"] = _row_event
    _has_explicit_when = False    # any When text found in spec
    _has_executable_when = False  # When text implies an actual function call
    # when_source: TESTSPEC_EXPLICIT when row expected_input provides When text; NONE otherwise.
    # Project memory / style example / default template When text is not authoritative.
    if _row_ei:
        _rg, _rw = _extract_given_when(_row_ei)
        if _rg:
            fields["given"] = _rg
        if _rw:
            fields["when"] = _rw
            _has_explicit_when = True
            _has_executable_when = bool(_EXECUTABLE_WHEN_RE.search(_rw))
        else:
            # No explicit When in spec — clear any Operation-derived When from generated comment.
            fields["when"] = ""
    else:
        # No expected_input at all — block-comment-derived When text is not testspec-authoritative.
        fields["when"] = ""
    if _row_eo:
        _rt = _extract_then(_row_eo)
        if _rt:
            fields["then"] = _rt

    canonical = _compact_block_comment(fields)

    # Rebuild pre: remove old block comment
    if pre_bc:
        pre = pre.replace(pre_bc, "", 1).strip()

    # Rebuild body: remove inner block comment and collapse leading blank lines to one newline
    if inner_bc:
        inner_clean = inner_text.replace(inner_bc, "", 1)
        inner_clean = re.sub(r"^(\s*\n)+", "\n", inner_clean)
        body = body[:head_end] + inner_clean

    # The testspec row is the sole authority for the When section.
    # Unconditionally overwrite any Copilot-generated // When: line (from style examples,
    # project memory, or default templates) with the canonical testspec When text.
    # Also removes any trailing bare igsw_Main_Run(); call that follows the comment.
    _when_auth = str(fields.get("when") or "")
    inner_body = body[head_end:]
    if _when_auth:
        inner_body = re.sub(
            r"([ \t]*)//[ \t]*When\s*:[^\n]*\n(?:[ \t]*igsw_Main_Run\s*\([^)]*\)\s*;\s*\n)?",
            lambda m: f"{m.group(1)}// When: {_when_auth}\n",
            inner_body,
        )
    else:
        inner_body = re.sub(
            r"([ \t]*)//[ \t]*When\s*:[^\n]*\n(?:[ \t]*igsw_Main_Run\s*\([^)]*\)\s*;\s*\n)?",
            r"\1// When: no explicit action in testspec\n",
            inner_body,
        )
    body = body[:head_end] + inner_body

    # Fill empty section labels
    body = _fill_section_labels(
        body,
        str(fields.get("given") or ""),
        str(fields.get("when") or ""),
        str(fields.get("then") or ""),
    )

    # When text exists but is a passive condition (not an executable call): add ALEX_REVIEW
    # after the // When: line so engineers know no action mapping is needed.
    if _has_explicit_when and not _has_executable_when:
        inner_body = body[head_end:]
        inner_body = re.sub(
            r"([ \t]*)//\s*When\s*:([^\n]*)\n",
            lambda m: (
                f"{m.group(1)}// When:{m.group(2)}\n"
                f"{m.group(1)}// ALEX_REVIEW: no executable action mapping for"
                f" When condition:{m.group(2)}\n"
            ),
            inner_body,
            count=1,
        )
        body = body[:head_end] + inner_body

    # Sanitize inner body: remove markdown bullets, bare igsw_Main_Run calls,
    # incomplete EXPECT_CALL blocks, and raw-signal EXPECT_THAT calls.
    # Memory-mapped output signals are exempt from the raw-signal Rule 5 replacement.
    inner_body = body[head_end:]
    inner_body = sanitize_generated_cpp_body(
        inner_body,
        has_explicit_when=_has_executable_when,
        mapped_output_signals=_mapped_out_sigs,
    )
    body = body[:head_end] + inner_body

    # Collapse 3+ consecutive blank lines in the TEST_F body to at most one blank line.
    inner_body = body[head_end:]
    inner_body = re.sub(r"\n{3,}", "\n\n", inner_body)
    body = body[:head_end] + inner_body

    # Reassemble: drop @alex: internal markers (they are not part of the
    # formatted output — save_draft re-adds them via wrap_markers at persist time).
    other_lines = [ln for ln in pre.splitlines() if not ln.strip().startswith("// @alex:")]

    parts: list[str] = []
    if other_lines:
        parts.append("\n".join(ln for ln in other_lines if ln.strip()))
    parts.append(canonical)
    parts.append(body.strip())

    return "\n".join(parts)
