"""Tests for representative style example extraction and prompt inclusion."""

from __future__ import annotations

from web.copilot_batch_codegen import (
    _style_example_score,
    build_copilot_batch_prompts,
    build_style_example_block,
    pick_representative_style_example,
)

# ---------------------------------------------------------------------------
# The real project style from the spec
# ---------------------------------------------------------------------------

_JAPANESE_TESTCASE = """\
/**
 * テストケース01：
 * 条件：
 *  - WMODE_CMD = 0
 *  - DRDYSTS = 0
 * 期待結果：
 *  - V_PMODE_STS = 0
 */
TEST_F(BasicPowerModeTest, InitialStateShouldRemainOff)
{
    // Given:
    EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD(NotNull()))
        .WillRepeatedly(DoAll(SetArgPointee<0>(0), Return(RTE_E_OK)));

    EXPECT_CALL(rte, Rte_Read_COMRX_DRDYSTS(NotNull()))
        .WillRepeatedly(DoAll(SetArgPointee<0>(0), Return(RTE_E_OK)));

    igsw_Main_Run();

    // When:
    igsw_Main_Run();

    // Then:
    EXPECT_THAT(V_PMODE_STS, Eq(0));
}
"""

_PLAIN_TESTCASE = """\
TEST_F(SomeFixture, SomeTest)
{
    EXPECT_EQ(foo(), 1);
}
"""

_GENERIC_TESTCASE = "TEST_F(F, T) { EXPECT_EQ(1, 1); }"


# ---------------------------------------------------------------------------
# 1. _style_example_score: prefer Japanese + EXPECT_CALL + Rte_Read + etc.
# ---------------------------------------------------------------------------

def test_japanese_snippet_scores_highest() -> None:
    s_jp = _style_example_score(_JAPANESE_TESTCASE)
    s_pl = _style_example_score(_PLAIN_TESTCASE)
    s_ge = _style_example_score(_GENERIC_TESTCASE)
    # Japanese testcase must score highest; plain and generic may tie at 0 but jp must win
    assert s_jp > s_ge, f"Expected jp({s_jp}) > generic({s_ge})"
    assert s_jp > s_pl or s_jp >= s_pl, f"Japanese score {s_jp} must not be below plain {s_pl}"
    assert s_jp > max(s_pl, s_ge), f"Japanese snippet must score strictly above both plain and generic: jp={s_jp}"


def test_score_awards_japanese_characters() -> None:
    with_jp = _style_example_score("TEST_F(F, T) { // テスト } ")
    without_jp = _style_example_score("TEST_F(F, T) { // comment } ")
    assert with_jp > without_jp


def test_score_awards_expect_call() -> None:
    with_ec = _style_example_score("TEST_F(F, T) { EXPECT_CALL(rte, Fn()); EXPECT_THAT(x, Eq(1)); }")
    without_ec = _style_example_score("TEST_F(F, T) { EXPECT_THAT(x, Eq(1)); }")
    assert with_ec > without_ec


def test_score_awards_rte_read() -> None:
    with_rr = _style_example_score("TEST_F(F, T) { Rte_Read_FOO(); }")
    without_rr = _style_example_score("TEST_F(F, T) { EXPECT_EQ(1, 1); }")
    assert with_rr > without_rr


# ---------------------------------------------------------------------------
# 2. pick_representative_style_example: selects best snippet
# ---------------------------------------------------------------------------

def test_picks_japanese_snippet_over_plain() -> None:
    samples = [
        {"snippet": _PLAIN_TESTCASE, "label": "plain.cc"},
        {"snippet": _JAPANESE_TESTCASE, "label": "japanese.cc"},
        {"snippet": _GENERIC_TESTCASE, "label": "generic.cc"},
    ]
    chosen = pick_representative_style_example(samples, slim_prompt=True)
    assert "テストケース" in chosen or "igsw_Main_Run" in chosen


def test_pick_returns_empty_for_no_samples() -> None:
    assert pick_representative_style_example([]) == ""
    assert pick_representative_style_example([{"snippet": "", "label": "x"}]) == ""


def test_pick_respects_char_limit() -> None:
    long_snippet = _JAPANESE_TESTCASE * 10  # very long
    samples = [{"snippet": long_snippet, "label": "s"}]
    result = pick_representative_style_example(samples, slim_prompt=True, char_limit=500)
    # _clip appends "...[trimmed for Copilot latency]" (32 chars) so allow up to char_limit + 40
    assert len(result) <= 540, f"Result length {len(result)} exceeds limit+40"
    assert len(result) < len(long_snippet), "Result must be shorter than original"


def test_pick_skips_non_test_f_snippet() -> None:
    samples = [{"snippet": "void helper() { return; }", "label": "util.cc"}]
    result = pick_representative_style_example(samples)
    assert result == ""


# ---------------------------------------------------------------------------
# 3. build_style_example_block: format
# ---------------------------------------------------------------------------

def test_style_example_block_contains_cpp_fence() -> None:
    block = build_style_example_block(_JAPANESE_TESTCASE, label="sample.cc")
    assert "```cpp" in block
    assert "テストケース" in block


def test_style_example_block_contains_style_rules() -> None:
    block = build_style_example_block(_JAPANESE_TESTCASE)
    assert "EXPECT_CALL" in block
    assert "Rte_Read" in block
    assert "igsw_Main_Run" in block
    assert "EXPECT_THAT" in block
    assert "WillRepeatedly" in block


def test_style_example_block_contains_japanese_rule() -> None:
    block = build_style_example_block(_JAPANESE_TESTCASE, label="jp_test.cc")
    assert "Japanese" in block or "japanese" in block.lower()


def test_style_example_block_empty_for_empty_snippet() -> None:
    assert build_style_example_block("") == ""


def test_style_example_block_includes_label() -> None:
    block = build_style_example_block(_PLAIN_TESTCASE, label="my_sample.cc")
    assert "my_sample.cc" in block


# ---------------------------------------------------------------------------
# 4. Prompt includes complete style example with all key patterns
# ---------------------------------------------------------------------------

def _make_prompt_with_japanese_sample() -> str:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_PM_001",
                "operation": {"given": [{"signal": "WMODE_CMD", "value": "1"}]},
                "expectation": [{"signal": "V_PMODE_STS", "value": "1"}],
            }
        ],
        "ai_assists": {
            "code_style_samples": [
                {"snippet": _JAPANESE_TESTCASE, "label": "sample_powermode.cc", "source_file": "sample_powermode.cc"},
            ],
            "workbook_overlays": {
                "TC_PM_001": {
                    "expected_input": "Given: WMODE_CMD=1, DRDYSTS=1",
                    "expected_output": "Then: V_PMODE_STS=1",
                }
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_PM_001"], allow_missing_sample=True
    )
    assert result["ok"] is True
    return result["prompts"][0]["prompt"]


def test_prompt_includes_complete_test_f_example() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "BasicPowerModeTest" in prompt, "fixture class must appear in prompt"
    assert "InitialStateShouldRemainOff" in prompt, "test name must appear in prompt"


def test_prompt_preserves_japanese_comment_block() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "テストケース" in prompt, "Japanese testcase comment must appear in prompt"
    assert "WMODE_CMD" in prompt


def test_prompt_includes_expect_call_rte_read_pattern() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "EXPECT_CALL" in prompt, "EXPECT_CALL must appear in style example"
    assert "Rte_Read" in prompt, "Rte_Read pattern must appear in style example"


def test_prompt_includes_igsw_main_run_pattern() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "igsw_Main_Run" in prompt, "igsw_Main_Run must appear in style example"


def test_prompt_includes_expect_that_eq_pattern() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "EXPECT_THAT" in prompt
    assert "Eq(" in prompt or "Eq(0)" in prompt


def test_prompt_includes_will_repeatedly_set_arg_pattern() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "WillRepeatedly" in prompt
    assert "SetArgPointee" in prompt


def test_style_example_section_header_present() -> None:
    prompt = _make_prompt_with_japanese_sample()
    assert "STYLE EXAMPLE" in prompt


def test_style_example_appears_before_testcase_rows() -> None:
    """The style example must appear before the testcase rows section."""
    prompt = _make_prompt_with_japanese_sample()
    style_pos = prompt.find("STYLE EXAMPLE")
    # Header changed from "Testcase rows for this API chunk" to "TESTCASES (N)"
    rows_pos = max(prompt.find("Testcase rows for"), prompt.find("TESTCASES ("))
    assert style_pos >= 0, "STYLE EXAMPLE must be in prompt"
    assert rows_pos >= 0, "Testcase rows section must be in prompt"
    assert style_pos < rows_pos, "Style example must appear before testcase rows"


def test_prompt_includes_strong_follow_style_wording() -> None:
    prompt = _make_prompt_with_japanese_sample()
    # Must include a rule about following the style example
    assert "STYLE EXAMPLE" in prompt
    assert "follow" in prompt.lower() or "Follow" in prompt


# ---------------------------------------------------------------------------
# 5. Budget trimming keeps style example
# ---------------------------------------------------------------------------

def test_style_example_not_dropped_at_slim_budget() -> None:
    """Style example must appear in prompt even at default slim budget (5000 chars)."""
    bundle = {
        "test_candidates": [
            {
                "id": f"TC_{i:03d}",
                "operation": {"given": [{"signal": "X", "value": str(i)}]},
                "expectation": [{"signal": "Y", "value": str(i)}],
            }
            for i in range(10)
        ],
        "ai_assists": {
            "code_style_samples": [
                {"snippet": _JAPANESE_TESTCASE, "label": "sample.cc", "source_file": "sample.cc"},
            ],
            "workbook_overlays": {
                f"TC_{i:03d}": {
                    "expected_input": f"Given: X={i}\n" * 3,
                    "expected_output": f"Then: Y={i}\n" * 3,
                }
                for i in range(10)
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, allow_missing_sample=True, slim_prompt=True, prompt_budget=5000
    )
    assert result["ok"] is True
    # Check at least one chunk has the Japanese style example
    found_in_any = any(
        "テストケース" in p["prompt"] or "igsw_Main_Run" in p["prompt"]
        for p in result["prompts"]
    )
    assert found_in_any, "Style example must appear in at least one chunk even under budget pressure"


def test_style_example_prioritised_over_saved_examples() -> None:
    """When budget is tight, the style example must NOT be dropped before saved examples."""
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "code_style_samples": [
                {"snippet": _JAPANESE_TESTCASE, "label": "sample.cc", "source_file": "sample.cc"},
            ],
            "workbook_overlays": {"TC_A": {"expected_input": "Given: X=1", "expected_output": "Then: Y=0"}},
        },
    }
    gtest_state: dict = {
        "drafts": {
            "TC_PREV": {
                "code_status": "SAVED",
                "full_snippet": "TEST_F(Fixture, TC_PREV) { EXPECT_EQ(out.x, 1); }",
                "code_body": "TEST_F(Fixture, TC_PREV) { EXPECT_EQ(out.x, 1); }",
            }
        },
        "project_code_config_cache": {},
    }
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True, slim_prompt=True
    )
    assert result["ok"] is True
    prompt = result["prompts"][0]["prompt"]
    assert "テストケース" in prompt or "igsw_Main_Run" in prompt, \
        "Style example from sample.cc must be in prompt"


# ---------------------------------------------------------------------------
# 6. No sample fallback still generates prompt
# ---------------------------------------------------------------------------

def test_prompt_generated_without_sample() -> None:
    """Prompt must still be generated when no sample .cc is loaded."""
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": [{"signal": "X", "value": "1"}]}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {"TC_A": {"expected_input": "Given: X=1", "expected_output": ""}},
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True
    prompt = result["prompts"][0]["prompt"]
    assert "TODO_REVIEW" in prompt, "No-sample fallback must still mention TODO_REVIEW"
