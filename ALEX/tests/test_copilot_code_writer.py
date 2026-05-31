"""Tests for Copilot GTest code writer (mocked M365)."""

from __future__ import annotations

from unittest.mock import patch

from web.code_style_samples import validate_gtest_code_for_save
from web.copilot_code_writer import (
    build_gtest_copilot_prompt,
    build_gtest_copilot_prompt_followup,
    parse_copilot_cpp_response,
    run_code_write,
)


def _minimal_pack() -> dict:
    return {
        "testcase": {
            "candidate_id": "TC_PM_004",
            "expected_input": "Given: A=1",
            "expected_output": "Then: B=0",
        },
        "harness": {"fixture_class": "T"},
        "io_variable_map": {},
        "verification_patterns": [],
        "sibling_assertions": [],
        "logic": {},
        "baseline_skeleton": {},
        "code_style_reference": {"samples": [{"label": "ref", "snippet": "TEST_F(T, x) { RunForMs(10); }"}]},
    }


def test_run_code_write_parses_json_legacy() -> None:
    pack = _minimal_pack()
    reply = '{"test_name": "TC1_test", "code_body": "TEST_F(T, TC1_test) { EXPECT_EQ(a,1); }", "full_snippet": "// TC_PM_004\\nTEST_F(T, TC1_test) { EXPECT_EQ(a,1); }"}'
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        out = run_code_write(pack, {})
    assert out["ok"] is True
    assert "TC1_test" in out["draft"]["full_snippet"]


def test_run_code_write_parses_cpp_fence() -> None:
    pack = _minimal_pack()
    reply = """```cpp
// TC_PM_004
TEST_F(T, my_test) {
  EXPECT_EQ(out.B, 0);
}
```
ASSUMPTIONS:
- Used RunForMs from sample
"""
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        out = run_code_write(pack, {})
    assert out["ok"] is True
    assert "TC_PM_004" in out["draft"]["full_snippet"]
    assert "EXPECT_EQ" in out["draft"]["full_snippet"]


def test_parse_copilot_cpp_response() -> None:
    text = "```cpp\nTEST_F(F, t) { EXPECT_TRUE(x); }\n```\nASSUMPTIONS:\n- ok\n"
    parsed = parse_copilot_cpp_response(text)
    assert "TEST_F" in parsed["full_snippet"]
    assert parsed["assumptions"] == ["ok"]


def test_build_gtest_copilot_prompt_includes_rules() -> None:
    prompt = build_gtest_copilot_prompt(_minimal_pack(), code_rule="Use RunForMs after When")
    assert "Code Rule / Change Request" in prompt
    assert "TC_PM_004" in prompt
    assert "Generate GTest C++ ONLY" in prompt


def test_followup_prompt_shorter_than_full() -> None:
    pack = _minimal_pack()
    full = build_gtest_copilot_prompt(pack, slim=True)
    follow = build_gtest_copilot_prompt_followup(pack, code_rule="Use RunForMs")
    assert len(follow) < len(full)
    assert "TC_PM_004" in follow
    assert "Same GTest style" in follow


def test_validate_gtest_code_for_save() -> None:
    code = "// TC_PM_004\nTEST_F(T, x) { EXPECT_EQ(a, 1); }"
    val = validate_gtest_code_for_save(code, candidate_id="TC_PM_004", sample_snippet="TEST_F(T,x){RunForMs(1);}")
    assert val["ok"] is True


def test_run_code_refine_accepts_skeleton_without_expect() -> None:
    existing = "// TC_PM_008\nTEST_F(T, t) { /* Then: OUT=1 */ }"
    reply = """```cpp
// TC_PM_008
TEST_F(T, t) {
  // Then: RELAY_MAIN=OFF
}
```"""
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        from web.copilot_code_writer import run_code_refine

        out = run_code_refine(existing, "convert SHUT_OFF line", {})
    assert out["ok"] is True
    assert "RELAY_MAIN" in out["draft"]["full_snippet"]
    assert "missing_EXPECT" in (out.get("validation") or {}).get("flags", [])


def test_run_code_write_returns_structured_error() -> None:
    pack = _minimal_pack()
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={
            "ok": False,
            "error": "no license",
            "error_category": "m365_not_entitled",
            "graph_status": 403,
        },
    ):
        out = run_code_write(pack, {})
    assert out["ok"] is False
    assert out["error_category"] == "m365_not_entitled"
