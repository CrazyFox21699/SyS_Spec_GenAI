"""M365 Copilot — generate GTest code from Code Context Pack."""

from __future__ import annotations

import json
from typing import Any

from web.code_style_samples import validate_copilot_code_draft
from web.m365_copilot import run_copilot_chat_result


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


def _format_style_samples(style_ref: dict[str, Any]) -> str:
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
    for row in samples[:3]:
        blocks.append(
            {
                "label": str(row.get("label") or row.get("test_name") or "ref"),
                "fixture": str(row.get("fixture_class") or ""),
                "snippet": str(row.get("snippet") or "")[:8000],
            }
        )
    return "\n".join(lines) + "\n\n" + json.dumps(blocks, ensure_ascii=False, indent=2)


def _writer_prompt(context_pack: dict[str, Any], *, engineer_note: str = "", copilot_prompt_override: str = "") -> str:
    tc = context_pack.get("testcase") or {}
    harness = context_pack.get("harness") or {}
    baseline = context_pack.get("baseline_skeleton") or {}
    patterns = context_pack.get("verification_patterns") or []
    siblings = context_pack.get("sibling_assertions") or []
    io_map = context_pack.get("io_variable_map") or {}
    logic = context_pack.get("logic") or {}
    style_ref = context_pack.get("code_style_reference") or {}
    style_text = _format_style_samples(style_ref)

    return (
        "You are Microsoft 365 Copilot writing Google Test (GTest) C++ for automotive ALEX.\n"
        "Write a complete TEST_F from the approved testcase spec below.\n\n"
        "Rules:\n"
        "- Match project reference code style (fixture, helpers, comment blocks).\n"
        "- Use harness fixture/members exactly as provided.\n"
        "- Map spec signals using io_variable_map when present; otherwise use harness members + spec names.\n"
        "- Every Then: line in expected_output MUST become an EXPECT_EQ or appropriate assert.\n"
        "- Given: lines become input assignments; When: timing becomes advance_time call.\n"
        "- Include spec comment block referencing candidate_id and control.\n"
        "- If verification_patterns list then_signals, assert ALL when Given matches.\n"
        "- If sibling_assertions show same Given with different Then, this case is one variant — "
        "assert only this testcase's expected_output.\n"
        "- Reference snippets are STYLE ONLY — never copy their literal values.\n\n"
        f"Engineer note: {engineer_note[:1500]}\n\n"
        f"Project reference GTest (style + helpers):\n{style_text[:12000]}\n\n"
        f"Harness:\n{json.dumps(harness, ensure_ascii=False)[:2000]}\n\n"
        f"io_variable_map:\n{json.dumps(io_map, ensure_ascii=False)[:3000]}\n\n"
        f"Logic:\n{json.dumps(logic, ensure_ascii=False)[:2000]}\n\n"
        f"Testcase:\n{json.dumps(tc, ensure_ascii=False)[:6000]}\n\n"
        f"Verification patterns:\n{json.dumps(patterns, ensure_ascii=False)[:2000]}\n\n"
        f"Sibling assertions (same Given):\n{json.dumps(siblings, ensure_ascii=False)[:1500]}\n\n"
        f"Python baseline skeleton (structure reference, improve with project style):\n"
        f"{json.dumps({k: baseline.get(k) for k in ('test_name', 'code_body', 'full_snippet') if baseline.get(k)}, ensure_ascii=False)[:4000]}\n\n"
        + (f"Additional Copilot instructions from engineer:\n{copilot_prompt_override[:4000]}\n\n" if copilot_prompt_override.strip() else "")
        + "Return JSON only:\n"
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
    copilot_prompt_override: str = "",
    reuse_conversation: bool = False,
) -> dict[str, Any]:
    prompt = _writer_prompt(
        context_pack,
        engineer_note=engineer_note,
        copilot_prompt_override=copilot_prompt_override,
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
    parsed = _parse_json_response(raw)
    if not parsed.get("full_snippet") and parsed.get("code_body"):
        comments = str(parsed.get("spec_comment_block") or "").strip()
        body = str(parsed.get("code_body") or "").strip()
        parsed["full_snippet"] = "\n".join(x for x in (comments, body) if x)
    tc = context_pack.get("testcase") or {}
    expected_name = str(tc.get("test_function") or tc.get("candidate_id") or "")
    validation = validate_copilot_code_draft(parsed, expected_test_name=expected_name)
    return {
        "ok": bool(parsed.get("full_snippet") or parsed.get("code_body")) and validation["ok"],
        "draft": parsed,
        "validation": validation,
        "raw_preview": raw[:500] if not parsed else "",
        "provider": "m365_copilot",
    }


def code_write_batch_size(cfg: dict[str, Any] | None) -> int:
    if not cfg:
        return 3
    assist = cfg.get("assist") or {}
    return max(1, min(8, int(assist.get("copilot_code_batch_size", assist.get("copilot_write_batch_size", 3)))))
