"""Tests for code_parser TEST_F extraction."""

from __future__ import annotations

from web.code_style_samples import (
    blocks_from_code_references,
    code_style_reference_for_bundle,
    ingest_cpp_upload,
    validate_copilot_code_draft,
)
from src.parsers.code_parser import extract_test_f_blocks, infer_harness_from_code, parse_cpp_upload

SAMPLE_CPP = """
class PowerModeTest : public ::testing::Test {
 protected:
  void SetUp() override {}
};

TEST_F(PowerModeTest, SampleReset) {
  in.RESET_SHUTOFF = 1U;
  RunForMs(0U);
  EvaluatePowerMode(state, in, out);
  EXPECT_EQ(out.SHUTOFF_DECISION, false);
}
"""


def test_extract_test_f_blocks() -> None:
    blocks = extract_test_f_blocks(SAMPLE_CPP)
    assert len(blocks) == 1
    assert blocks[0]["test_name"] == "SampleReset"
    assert blocks[0]["fixture_class"] == "PowerModeTest"
    assert "EXPECT_EQ" in blocks[0]["snippet"]


def test_infer_harness_from_code() -> None:
    hints = infer_harness_from_code(SAMPLE_CPP)
    assert hints.get("fixture_class") == "PowerModeTest"
    assert hints.get("inputs_member") == "in"
    assert hints.get("outputs_member") == "out"
    assert hints.get("evaluate_fn") == "EvaluatePowerMode"


def test_ingest_cpp_upload() -> None:
    bundle: dict = {"ai_assists": {}}
    gtest_state: dict = {"harness": {}}
    result = ingest_cpp_upload(bundle, gtest_state, content=SAMPLE_CPP, filename="sample.cpp")
    assert len(result["samples"]) >= 1
    assert gtest_state["harness"].get("fixture_class") == "PowerModeTest"


def test_blocks_from_code_references() -> None:
    refs = [
        {
            "file": "t.cpp",
            "test_blocks": extract_test_f_blocks(SAMPLE_CPP),
            "harness_hints": infer_harness_from_code(SAMPLE_CPP),
        }
    ]
    rows = blocks_from_code_references(refs)
    assert rows[0]["test_name"] == "SampleReset"


def test_code_style_reference_primary() -> None:
    bundle = {
        "ai_assists": {
            "code_style_samples": [
                {"label": "a", "test_name": "SampleReset", "snippet": SAMPLE_CPP},
            ]
        }
    }
    ref = code_style_reference_for_bundle(bundle, reference_test_name="SampleReset")
    assert ref["sample_count"] == 1
    assert ref["primary_reference"]["test_name"] == "SampleReset"


def test_validate_copilot_code_draft() -> None:
    ok = validate_copilot_code_draft(
        {"full_snippet": "TEST_F(T, x) { EXPECT_EQ(a, 1); }", "code_body": ""},
    )
    assert ok["ok"] is True
    bad = validate_copilot_code_draft({"full_snippet": "// empty"})
    assert bad["ok"] is False


def test_parse_cpp_upload() -> None:
    parsed = parse_cpp_upload(SAMPLE_CPP, filename="x.cpp")
    assert parsed["test_blocks"]
    assert parsed["harness_hints"]["fixture_class"] == "PowerModeTest"
