"""M365 Copilot — generate GTest code from Code Context Pack."""

from __future__ import annotations

import json
from typing import Any

from web.m365_copilot import run_copilot_chat


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


def _writer_prompt(context_pack: dict[str, Any], *, engineer_note: str = "") -> str:
    tc = context_pack.get("testcase") or {}
    harness = context_pack.get("harness") or {}
    baseline = context_pack.get("baseline_skeleton") or {}
    patterns = context_pack.get("verification_patterns") or []
    siblings = context_pack.get("sibling_assertions") or []
    io_map = context_pack.get("io_variable_map") or {}
    logic = context_pack.get("logic") or {}

    return (
        "You are Microsoft 365 Copilot writing Google Test (GTest) C++ for automotive ALEX.\n"
        "Write a complete TEST_F from the approved testcase spec below.\n\n"
        "Rules:\n"
        "- Use harness fixture/members exactly as provided.\n"
        "- Map spec signals using io_variable_map; do not invent code symbol names.\n"
        "- Every Then: line in expected_output MUST become an EXPECT_EQ or appropriate assert.\n"
        "- Given: lines become input assignments; When: timing becomes advance_time call.\n"
        "- Include spec comment block referencing candidate_id and control.\n"
        "- If verification_patterns list then_signals, assert ALL when Given matches.\n"
        "- If sibling_assertions show same Given with different Then, this case is one variant — "
        "assert only this testcase's expected_output.\n\n"
        f"Engineer note: {engineer_note[:1500]}\n\n"
        f"Harness:\n{json.dumps(harness, ensure_ascii=False)[:2000]}\n\n"
        f"io_variable_map:\n{json.dumps(io_map, ensure_ascii=False)[:3000]}\n\n"
        f"Logic:\n{json.dumps(logic, ensure_ascii=False)[:2000]}\n\n"
        f"Testcase:\n{json.dumps(tc, ensure_ascii=False)[:6000]}\n\n"
        f"Verification patterns:\n{json.dumps(patterns, ensure_ascii=False)[:2000]}\n\n"
        f"Sibling assertions (same Given):\n{json.dumps(siblings, ensure_ascii=False)[:1500]}\n\n"
        f"Python baseline skeleton (reference, improve if needed):\n"
        f"{json.dumps({k: baseline.get(k) for k in ('test_name', 'code_body', 'full_snippet') if baseline.get(k)}, ensure_ascii=False)[:4000]}\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "test_name": "TEST_F name suffix",\n'
        '  "spec_comment_block": "// ...",\n'
        '  "code_body": "TEST_F(...) { ... }",\n'
        '  "full_snippet": "// comments\\nTEST_F(...)",\n'
        '  "assumptions": [],\n'
        '  "open_questions": []\n'
        "}"
    )


def run_code_write(
    context_pack: dict[str, Any],
    cfg: dict[str, Any],
    *,
    engineer_note: str = "",
) -> dict[str, Any]:
    prompt = _writer_prompt(context_pack, engineer_note=engineer_note)
    raw = run_copilot_chat(cfg, prompt)
    parsed = _parse_json_response(raw)
    if not parsed.get("full_snippet") and parsed.get("code_body"):
        comments = str(parsed.get("spec_comment_block") or "").strip()
        body = str(parsed.get("code_body") or "").strip()
        parsed["full_snippet"] = "\n".join(x for x in (comments, body) if x)
    return {
        "ok": bool(parsed.get("full_snippet") or parsed.get("code_body")),
        "draft": parsed,
        "raw_preview": raw[:500] if not parsed else "",
        "provider": "m365_copilot",
    }
