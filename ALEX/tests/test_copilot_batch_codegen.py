"""Copilot batch orchestrator — prompt, parse, import."""

from __future__ import annotations

from pathlib import Path

from web.copilot_batch_codegen import (
    apply_copilot_batch_import,
    build_copilot_batch_prompts,
    collect_copilot_project_context,
    parse_copilot_batch_response,
)

BATCH_OUT = """
[TESTCASE_CODE]
testcase_id: TC_A
```cpp
// TC_A
TEST_F(RteDefaultAction, A) {
  EXPECT_CALL(rte, Rte_Read_FOO(NotNull())).WillRepeatedly(Return(RTE_E_OK));
  igsw_Main_Run();
  EXPECT_THAT(V_OUT, Eq(1));
}
```
[UNRESOLVED]
testcase_id: TC_B
reason: missing mock for SIG_X
[ASSUMPTIONS]
- used exemplar fixture
"""


def test_parse_unresolved_per_id() -> None:
    p = parse_copilot_batch_response(BATCH_OUT)
    assert p["parsed_count"] == 1
    assert "TC_A" in {i["candidate_id"] for i in p["items"]}
    assert p["unresolved_by_id"].get("TC_B")


def test_build_prompt_requires_sample_or_saved() -> None:
    from web.copilot_batch_codegen import build_copilot_batch_prompt

    bundle = {"test_candidates": []}
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}
    r = build_copilot_batch_prompts(bundle, gtest_state, candidate_ids=["TC_A"])
    assert r["ok"] is False

    bundle["ai_assists"] = {"code_style_samples": [{"label": "s", "snippet": "TEST_F(F, T) { igsw_Main_Run(); }"}]}
    ctx = collect_copilot_project_context(bundle, gtest_state)
    assert ctx["sample_blocks"]
    prompt = build_copilot_batch_prompt(
        ctx,
        [{"candidate_id": "TC_A", "expected_input": "Given: X", "expected_output": "Then: Y"}],
    )
    assert "[TESTCASE_CODE]" in prompt
    assert "[UNRESOLVED]" in prompt
    assert "Do not change grouping" in prompt


def test_apply_marks_unresolved_error(tmp_path: Path) -> None:
    bundle = {
        "test_candidates": [
            {"candidate_id": "TC_A", "expected_input": "Given: X", "expected_output": "Then: Y"},
            {"candidate_id": "TC_B", "expected_input": "Given: Z", "expected_output": "Then: W"},
        ],
        "ai_assists": {"code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}]},
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}
    out = apply_copilot_batch_import(
        bundle,
        gtest_state,
        tmp_path,
        content=BATCH_OUT,
        expected_candidate_ids=["TC_A", "TC_B"],
    )
    by_id = {r["candidate_id"]: r for r in out.get("results") or []}
    assert by_id["TC_B"]["workflow_status"] == "ERROR"
    assert by_id["TC_A"]["workflow_status"] in ("SAVED", "NEEDS_REVIEW", "DRAFT")
