"""Tests for Copilot GTest code writer (mocked M365)."""

from __future__ import annotations

from unittest.mock import patch

from web.copilot_code_writer import run_code_write


def test_run_code_write_parses_json() -> None:
    pack = {
        "testcase": {"candidate_id": "TC1", "expected_input": "Given: A=1", "expected_output": "Then: B=0"},
        "harness": {"fixture_class": "T"},
        "io_variable_map": {},
        "verification_patterns": [],
        "sibling_assertions": [],
        "logic": {},
        "baseline_skeleton": {},
    }
    reply = '{"test_name": "TC1_test", "code_body": "TEST_F(T, TC1_test) {}", "full_snippet": "// c\\nTEST_F(T, TC1_test) {}"}'
    with patch("web.copilot_code_writer.run_copilot_chat", return_value=reply):
        out = run_code_write(pack, {})
    assert out["ok"] is True
    assert "TC1_test" in out["draft"]["full_snippet"]
