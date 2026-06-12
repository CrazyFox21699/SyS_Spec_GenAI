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

_BC_FIELD_KEYS = ("testcase_id", "event", "test design", "given", "when", "then")

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
    """Build a compact ``/* … */`` block comment from a fields dict."""
    _LABELS = [
        ("testcase_id", "testcase_id"),
        ("event", "event"),
        ("test_design", "Test design"),
        ("given", "Given"),
        ("when", "When"),
        ("then", "Then"),
    ]
    lines = ["/*"]
    for key, label in _LABELS:
        val = str(fields.get(key) or "").strip()
        if val:
            lines.append(f" * {label}: {val}")
    lines.append(" */")
    return "\n".join(lines)


def _fill_section_labels(code: str, given: str, when: str, then: str) -> str:
    """Replace empty ``// Given:``, ``// When:``, ``// Then:`` lines with actual text."""
    vals: dict[str, str] = {"Given": given, "When": when, "Then": then}

    def _rep(m: re.Match) -> str:  # type: ignore[type-arg]
        indent = m.group(1)
        label = m.group(2)
        val = vals.get(label, "")
        return f"{indent}// {label}: {val}" if val else m.group(0)

    return re.compile(r"([ \t]*)//\s*(Given|When|Then)\s*:\s*$", re.MULTILINE).sub(_rep, code)


def normalize_testf_snippet(snippet: str, row: dict[str, Any] | None = None) -> str:
    """Normalize comment style in a generated TEST_F snippet.

    - If a design block comment (containing testcase_id/event/Given/When/Then)
      is found inside the TEST_F body, move it to before TEST_F.
    - Reformat any such block comment to compact single-line-per-field style.
    - Fill empty ``// Given:``, ``// When:``, ``// Then:`` section labels using
      field values from the block comment or from the row metadata fallback.
    - Code body (EXPECT_CALL, igsw_Main_Run, EXPECT_THAT) is not modified.
    - ``@alex:begin`` / ``@alex:spec_hash`` lines (if already present) are
      preserved above the block comment.

    Returns the snippet unchanged when there is nothing to normalize.
    """
    row = row or {}
    if not snippet:
        return snippet
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

    # Nothing to normalize if no design block comment found anywhere
    if not inner_bc and not pre_bc:
        return snippet

    # Rebuild fields from row metadata — row spec is authoritative when available.
    # This prevents malformed Copilot comments (e.g. event containing "Test design / purpose:")
    # from corrupting the final block comment.
    # Operation is NAMESPACE METADATA ONLY — never used as When.
    _row_cid = str(row.get("candidate_id") or row.get("id") or "").strip()
    _row_event = str(row.get("event") or row.get("test_function") or "").strip()
    _row_ei = str(row.get("expected_input") or "").strip()
    _row_eo = str(row.get("expected_output") or "").strip()

    if _row_cid:
        fields["testcase_id"] = _row_cid
    if _row_event:
        fields["event"] = _row_event
    _has_explicit_when = False
    if _row_ei:
        _rg, _rw = _extract_given_when(_row_ei)
        if _rg:
            fields["given"] = _rg
        if _rw:
            fields["when"] = _rw
            _has_explicit_when = True
        else:
            # No explicit When in spec — clear any Operation-derived When from generated comment.
            fields["when"] = ""
    if _row_eo:
        _rt = _extract_then(_row_eo)
        if _rt:
            fields["then"] = _rt

    # Generate test_design from spec data if not already present
    if not fields.get("test_design"):
        _g1 = str(fields.get("given") or "").split(";")[0].strip()[:60].rstrip(".")
        _t1 = str(fields.get("then") or "").split(";")[0].strip()[:80].rstrip(".")
        if _t1 and _g1:
            fields["test_design"] = f"Verify that {_t1} when {_g1}."
        elif _t1:
            fields["test_design"] = f"Verify that {_t1}."

    canonical = _compact_block_comment(fields)

    # Rebuild pre: remove old block comment
    if pre_bc:
        pre = pre.replace(pre_bc, "", 1).strip()

    # Rebuild body: remove inner block comment and collapse leading blank lines to one newline
    if inner_bc:
        inner_clean = inner_text.replace(inner_bc, "", 1)
        inner_clean = re.sub(r"^(\s*\n)+", "\n", inner_clean)
        body = body[:head_end] + inner_clean

    # Strip // When: body comment lines that were generated from Operation metadata.
    # Operation is namespace-only — any // When: in the body is invalid unless the spec
    # has an explicit executable When field.
    if not _has_explicit_when:
        inner_body = body[head_end:]
        # Remove "// When: ..." line and the igsw_Main_Run(); call immediately following it
        # (both are injected from Operation + default_main_function, not from executable spec).
        inner_body = re.sub(
            r"[ \t]*//[ \t]*When\s*:[^\n]*\n(?:[ \t]*igsw_Main_Run\s*\([^)]*\)\s*;\s*\n)?",
            "",
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

    # Reassemble: preserve @alex lines, then canonical block, then TEST_F
    alex_lines: list[str] = []
    other_lines: list[str] = []
    for line in pre.splitlines():
        (alex_lines if line.strip().startswith("// @alex:") else other_lines).append(line)

    parts: list[str] = []
    if alex_lines:
        parts.append("\n".join(alex_lines))
    if other_lines:
        parts.append("\n".join(ln for ln in other_lines if ln.strip()))
    parts.append(canonical)
    parts.append(body.strip())

    return "\n".join(parts)
