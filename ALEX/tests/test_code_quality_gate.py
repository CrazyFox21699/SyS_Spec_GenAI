"""Tests for deterministic GTest quality gate."""

from __future__ import annotations

from web.code_quality_gate import quality_to_code_status, run_quality_gate


def test_quality_gate_pass_minimal() -> None:
    code = "// TC_PM_001\nTEST_F(F, TC_PM_001) { EXPECT_EQ(1, 1); }"
    qg = run_quality_gate(code, candidate_id="TC_PM_001")
    assert qg["summary"] == "PASS"
    assert quality_to_code_status("PASS") == "SAVED"


def test_quality_gate_fail_fence() -> None:
    code = "```cpp\nTEST_F(F, t) { EXPECT_EQ(1,1); }\n```"
    qg = run_quality_gate(code, candidate_id="TC_PM_002")
    assert qg["summary"] == "FAIL"
    assert any(c["check_name"] == "markdown_fence" for c in qg["checks"])


def test_quality_gate_unknown_api() -> None:
    code = "// TC_PM_003\nTEST_F(F, TC_PM_003) { NotInCatalog(); EXPECT_EQ(1, 1); }"
    catalog = "apis:\n  - EXPECT_EQ\n  - TEST_F\n"
    qg = run_quality_gate(
        code,
        candidate_id="TC_PM_003",
        api_catalog_yaml=catalog,
    )
    assert any(c["check_name"] == "unknown_api" for c in qg["checks"])


def test_quality_to_code_status_mapping() -> None:
    assert quality_to_code_status("PASS") == "SAVED"
    assert quality_to_code_status("WARNING") == "NEEDS_REVIEW"
    assert quality_to_code_status("FAIL") == "ERROR"
