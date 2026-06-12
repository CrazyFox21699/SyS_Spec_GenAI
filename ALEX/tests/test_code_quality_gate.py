"""Tests for deterministic GTest quality gate."""

from __future__ import annotations

from web.code_quality_gate import is_fallback_scaffold, quality_to_code_status, run_quality_gate


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


# ---------------------------------------------------------------------------
# New tests per spec items 1 / 5 / 6
# ---------------------------------------------------------------------------

_FALLBACK_SCAFFOLD = (
    '// TC_A\n'
    '// NEEDS_REVIEW: Copilot API fallback scaffold.\n'
    'TEST(AlexGeneratedFallback, TC_A) {\n'
    '  GTEST_SKIP() << "NEEDS_REVIEW: Microsoft endpoint timed out.";\n'
    '}'
)


def test_fallback_scaffold_detection() -> None:
    """is_fallback_scaffold must detect GTEST_SKIP NEEDS_REVIEW pattern."""
    assert is_fallback_scaffold(_FALLBACK_SCAFFOLD) is True
    assert is_fallback_scaffold("TEST_F(F, T) { EXPECT_EQ(1,1); }") is False
    assert is_fallback_scaffold("") is False


def test_fallback_scaffold_quality_gate_returns_fail() -> None:
    """Quality gate on fallback scaffold must return FAIL (→ ERROR) to block save."""
    qg = run_quality_gate(_FALLBACK_SCAFFOLD, candidate_id="TC_A")
    assert qg["summary"] == "FAIL", "fallback scaffold must be FAIL so it cannot be saved"
    assert any(c["check_name"] == "fallback_scaffold" for c in qg["checks"])
    assert quality_to_code_status(qg["summary"]) == "ERROR"


def test_fallback_scaffold_not_saved() -> None:
    """A fallback scaffold must never be classified as SAVED."""
    status = quality_to_code_status(run_quality_gate(_FALLBACK_SCAFFOLD)["summary"])
    assert status != "SAVED"


def test_generated_code_with_warnings_is_needs_review_not_error() -> None:
    """Real generated code with quality warnings → NEEDS_REVIEW, not ERROR."""
    code_with_warnings = "// TC_X\nTEST_F(Fixture, TC_X) { SomeUnknownCall(); EXPECT_EQ(1, 1); }"
    qg = run_quality_gate(code_with_warnings, candidate_id="TC_X",
                          api_catalog_yaml="apis:\n  - EXPECT_EQ\n")
    # Has unknown API warning but code has TEST_F → should be WARNING, not FAIL
    assert qg["summary"] in ("WARNING", "PASS"), "warnings must not produce ERROR"
    assert quality_to_code_status(qg["summary"]) != "ERROR"


def test_missing_expect_is_warning_not_fail() -> None:
    """Missing EXPECT/ASSERT is a WARNING (NEEDS_REVIEW), not a FAIL (ERROR)."""
    code = "// TC_X\nTEST_F(F, TC_X) { SomeSetup(); }"
    qg = run_quality_gate(code, candidate_id="TC_X")
    warn_names = {c["check_name"] for c in qg["checks"] if c["severity"] == "WARNING"}
    assert "missing_EXPECT" in warn_names
    assert qg["summary"] != "FAIL", "missing EXPECT must be WARNING, not FAIL"


def test_sample_missing_does_not_block_quality_gate() -> None:
    """Quality gate should not fail just because sample_snippet is empty."""
    code = "// TC_X\nTEST_F(F, TC_X) { EXPECT_EQ(1, 1); }"
    qg = run_quality_gate(code, candidate_id="TC_X", sample_snippet="")
    assert qg["summary"] == "PASS"
