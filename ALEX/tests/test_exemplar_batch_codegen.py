"""Exemplar batch prompt build and response parse."""

from __future__ import annotations

from web.exemplar_batch_codegen import (
    apply_exemplar_batch_import,
    build_exemplar_batch_prompt,
    mark_code_exemplar,
    parse_exemplar_batch_response,
)

SAMPLE_BATCH = """
[TESTCASE_CODE]
testcase_id: TC_A
```cpp
// TC_A
TEST_F(RteDefaultAction, TC_A_Test) {
  EXPECT_CALL(rte, Rte_Read_FOO(NotNull()));
  igsw_Main_Run();
  EXPECT_THAT(V_OUT, Eq(1));
}
```
testcase_id: TC_B
```cpp
// TC_B
TEST_F(RteDefaultAction, TC_B_Test) {
  EXPECT_CALL(rte, Rte_Read_BAR(NotNull()));
  igsw_Main_Run();
  EXPECT_THAT(V_OUT2, Eq(2));
}
```
[ASSUMPTIONS]
- same fixture as exemplar
[UNRESOLVED]
none
"""


def test_parse_exemplar_batch_response() -> None:
    parsed = parse_exemplar_batch_response(SAMPLE_BATCH)
    assert parsed["ok"] is True
    assert parsed["parsed_count"] == 2
    ids = {i["candidate_id"] for i in parsed["items"]}
    assert ids == {"TC_A", "TC_B"}


def test_build_exemplar_batch_prompt() -> None:
    ex = {
        "candidate_id": "TC_EX",
        "expected_input": "Given: X = 1",
        "expected_output": "Then: Y = 1",
        "generated_code": "TEST_F(Fix, Ex) { }",
        "style_notes": "fixture=Fix",
        "sample_snippet": "",
    }
    prompt = build_exemplar_batch_prompt(
        ex,
        [{"candidate_id": "TC_A", "expected_input": "Given: A", "expected_output": "Then: B"}],
    )
    assert "TC_EX" in prompt
    assert "[TESTCASE_CODE]" in prompt
    assert "Do not change grouping" in prompt
    assert "EXACTLY" in prompt


def test_mark_and_apply_exemplar_batch(tmp_path) -> None:
    bundle = {
        "test_candidates": [
            {
                "candidate_id": "TC_EX",
                "expected_input": "Given: X = 1",
                "expected_output": "Then: Y = 1",
            },
            {
                "candidate_id": "TC_A",
                "expected_input": "Given: A = 1",
                "expected_output": "Then: B = 1",
            },
        ],
    }
    gtest_state = {
        "drafts": {
            "TC_EX": {
                "full_snippet": "// TC_EX\nTEST_F(RteDefaultAction, Ex) { igsw_Main_Run(); }",
                "code_status": "SAVED",
            }
        },
        "project_code_config_cache": {},
    }
    mk = mark_code_exemplar(bundle, gtest_state, "TC_EX", language="EN")
    assert mk["ok"] is True

    applied = apply_exemplar_batch_import(
        bundle,
        gtest_state,
        tmp_path,
        content=SAMPLE_BATCH,
        expected_candidate_ids=["TC_A"],
        language="EN",
    )
    assert applied.get("summary", {}).get("total") == 1
    assert "TC_A" in (gtest_state.get("drafts") or {})
