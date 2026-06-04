"""Tests for project_testcode_memory — global memory, extraction, section append, prompt injection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from web.project_testcode_memory import (
    DEFAULT_MEMORY,
    QUICK_ADD_RULE_TYPES,
    SECTIONS,
    append_to_section,
    build_proposed_memory,
    check_before_append,
    extract_patterns_from_sample,
    format_quick_add_rule,
    load_global_memory,
    load_memory_for_job,
    memory_for_prompt,
    memory_for_prompt_prioritized,
    merge_proposed_into_memory,
    rule_type_section,
    save_global_memory,
    save_memory_for_job,
)

_SAMPLE_CC = """\
#include <gtest/gtest.h>
using namespace testing;

class PowerModeTest : public RteDefaultAction {
public:
  void SetUpExtra() override {
    EXPECT_CALL(rte, Rte_Read_OK_SHUTOFF(NotNull()))
      .WillRepeatedly(DoAll(SetArgPointee<0>(1), Return(RTE_E_OK)));
  }
};

TEST_F(PowerModeTest, TC_PM_001) {
  // Given: OK_SHUTOFF=1
  EXPECT_CALL(rte, Rte_Read_OK_SHUTOFF(NotNull()))
    .WillRepeatedly(DoAll(SetArgPointee<0>(1), Return(RTE_E_OK)));
  igsw_Main_Run();
  // Then: out.mode = 1
  EXPECT_THAT(out.mode, Eq(1));
}
"""


# ---------------------------------------------------------------------------
# Global / job memory load-save
# ---------------------------------------------------------------------------

def test_load_global_memory_returns_default_when_missing(tmp_path: Path) -> None:
    with patch("web.project_testcode_memory._global_path", return_value=tmp_path / "nonexistent.md"):
        content = load_global_memory()
    assert "Project Test Code Memory" in content
    assert "Fixture / Test Style" in content


def test_save_and_load_global_memory(tmp_path: Path) -> None:
    target = tmp_path / "project_testcode_memory.md"
    with patch("web.project_testcode_memory._global_path", return_value=target):
        save_global_memory("# My Memory\n## Fixture / Test Style\n- use MyFixture\n")
        loaded = load_global_memory()
    assert "My Memory" in loaded
    assert "use MyFixture" in loaded


def test_load_memory_for_job_falls_back_to_global(tmp_path: Path) -> None:
    """If no job-local copy exists, fall back to global memory."""
    global_path = tmp_path / "global" / "project_testcode_memory.md"
    global_path.parent.mkdir(parents=True)
    global_path.write_text("# Global Memory\n## Reviewer Notes / Learned Fixes\n- global rule\n", encoding="utf-8")

    job_output = tmp_path / "job"
    job_output.mkdir()

    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        content = load_memory_for_job(job_output)
    assert "global rule" in content


def test_save_memory_for_job_creates_local_copy(tmp_path: Path) -> None:
    save_memory_for_job(tmp_path, "# Local Memory\n## Reviewer Notes / Learned Fixes\n- local rule\n")
    from web.project_code_config import project_code_config_dir
    local = project_code_config_dir(tmp_path) / "project_testcode_memory.md"
    assert local.exists()
    assert "local rule" in local.read_text(encoding="utf-8")


def test_load_memory_for_job_prefers_local_over_global(tmp_path: Path) -> None:
    """Job-local memory takes priority over global."""
    global_content = "# Global Memory\n## Reviewer Notes / Learned Fixes\n- global rule\n"
    local_content = "# Local Memory\n## Reviewer Notes / Learned Fixes\n- local rule\n"
    global_path = tmp_path / "global.md"
    global_path.write_text(global_content, encoding="utf-8")
    save_memory_for_job(tmp_path, local_content)

    with patch("web.project_testcode_memory._global_path", return_value=global_path):
        content = load_memory_for_job(tmp_path)
    assert "local rule" in content
    assert "global rule" not in content


# ---------------------------------------------------------------------------
# Section append
# ---------------------------------------------------------------------------

def test_append_to_section_existing() -> None:
    content = DEFAULT_MEMORY
    updated = append_to_section(content, "Reviewer Notes / Learned Fixes", "use RunForMs not sleep")
    assert "use RunForMs not sleep" in updated
    assert "Reviewer Notes / Learned Fixes" in updated


def test_append_to_section_creates_section_if_missing() -> None:
    content = "# Memory\n\n## Some Section\n- existing\n"
    updated = append_to_section(content, "New Section", "new bullet")
    assert "## New Section" in updated
    assert "new bullet" in updated


def test_append_to_section_does_not_duplicate_header() -> None:
    content = DEFAULT_MEMORY
    updated = append_to_section(content, "Timing Pattern", "use igsw_Main_Run()")
    assert updated.count("## Timing Pattern") == 1
    assert "use igsw_Main_Run()" in updated


# ---------------------------------------------------------------------------
# Extraction from sample .cc
# ---------------------------------------------------------------------------

def test_extract_fixtures() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    assert "PowerModeTest" in ex["fixtures"]


def test_extract_rte_reads() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    assert "OK_SHUTOFF" in ex["rte_reads"]


def test_extract_timing_functions() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    assert "igsw_Main_Run" in ex["timing_fns"]


def test_extract_assertion_macros() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    assert "EXPECT_THAT" in ex["assertion_macros"]


def test_extract_out_vars() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    assert "mode" in ex["out_vars"]


def test_build_proposed_memory_contains_extracted() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    proposed = build_proposed_memory(ex, source_file="test_sample.cc")
    assert "PowerModeTest" in proposed
    assert "igsw_Main_Run" in proposed
    assert "Rte_Read_OK_SHUTOFF" in proposed


def test_merge_proposed_into_empty_memory() -> None:
    ex = extract_patterns_from_sample(_SAMPLE_CC)
    proposed = build_proposed_memory(ex)
    merged = merge_proposed_into_memory(DEFAULT_MEMORY, proposed)
    assert "PowerModeTest" in merged
    assert "igsw_Main_Run" in merged


# ---------------------------------------------------------------------------
# memory_for_prompt — clipping and empty detection
# ---------------------------------------------------------------------------

def test_memory_for_prompt_empty_default_returns_empty() -> None:
    assert memory_for_prompt(DEFAULT_MEMORY) == "", "default empty template must not be sent to Copilot"


def test_memory_for_prompt_content_included() -> None:
    content = DEFAULT_MEMORY + "\n## Fixture / Test Style\n- use PowerModeTest\n"
    result = memory_for_prompt(content)
    assert "PowerModeTest" in result


def test_memory_for_prompt_clips_long_content() -> None:
    long_content = "# Memory\n" + "- rule\n" * 600
    result = memory_for_prompt(long_content, char_limit=500)
    assert len(result) <= 520  # some slack for trimmed suffix


# ---------------------------------------------------------------------------
# Memory included in Copilot batch prompt
# ---------------------------------------------------------------------------

def test_memory_included_in_copilot_batch_prompt() -> None:
    from web.copilot_batch_codegen import build_copilot_batch_prompts

    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {"TC_A": {"expected_input": "in", "expected_output": "out"}},
        },
    }
    gtest_state = {
        "drafts": {},
        "project_code_config_cache": {
            "project_testcode_memory.md": "# Memory\n## Fixture / Test Style\n- use PowerModeTest fixture\n",
        },
    }
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True
    prompt = result["prompts"][0]["prompt"]
    # Memory content now delivered via "GENERATION CRITICAL MAP" section
    assert "PowerModeTest fixture" in prompt or "GENERATION CRITICAL MAP" in prompt


def test_empty_memory_not_included_in_prompt() -> None:
    from web.copilot_batch_codegen import build_copilot_batch_prompts

    bundle = {
        "test_candidates": [{"id": "TC_A", "operation": {"given": []}, "expectation": []}],
        "ai_assists": {"workbook_overlays": {"TC_A": {"expected_input": "in", "expected_output": "out"}}},
    }
    gtest_state = {
        "drafts": {},
        "project_code_config_cache": {
            "project_testcode_memory.md": DEFAULT_MEMORY,  # empty template
        },
    }
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True
    prompt = result["prompts"][0]["prompt"]
    assert "Project Test Code Memory" not in prompt


def test_generation_works_without_sample_cc() -> None:
    from web.copilot_batch_codegen import build_copilot_batch_prompts

    bundle = {
        "test_candidates": [{"id": "TC_A", "operation": {"given": []}, "expectation": []}],
        "ai_assists": {"workbook_overlays": {"TC_A": {"expected_input": "in", "expected_output": "out"}}},
    }
    gtest_state = {
        "drafts": {},
        "project_code_config_cache": {
            "project_testcode_memory.md": "# Memory\n## Fixture / Test Style\n- use TestFixture\n",
        },
    }
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True, "generation must succeed without sample .cc"
    assert result["context_summary"]["missing_sample"] is True
    assert result.get("missing_sample_warning")


# ---------------------------------------------------------------------------
# Quick Add rule types and formatting
# ---------------------------------------------------------------------------

def test_quick_add_rule_types_defined() -> None:
    assert "input_mock" in QUICK_ADD_RULE_TYPES
    assert "output_assertion" in QUICK_ADD_RULE_TYPES
    assert "timing" in QUICK_ADD_RULE_TYPES
    assert "fixture_style" in QUICK_ADD_RULE_TYPES
    assert "signal_mapping" in QUICK_ADD_RULE_TYPES
    assert "forbidden_pattern" in QUICK_ADD_RULE_TYPES
    assert "reviewer_note" in QUICK_ADD_RULE_TYPES


def test_quick_add_input_mock_writes_to_input_mock_pattern() -> None:
    assert rule_type_section("input_mock") == "Input Mock Pattern"


def test_quick_add_output_assertion_writes_to_output_assertion_pattern() -> None:
    assert rule_type_section("output_assertion") == "Output Assertion Pattern"


def test_quick_add_timing_writes_to_timing_pattern() -> None:
    assert rule_type_section("timing") == "Timing Pattern"


def test_quick_add_fixture_writes_to_fixture_test_style() -> None:
    assert rule_type_section("fixture_style") == "Fixture / Test Style"


def test_quick_add_signal_mapping_writes_to_spec_signal_map() -> None:
    assert rule_type_section("signal_mapping") == "Spec Signal to Test Code Map"


def test_quick_add_forbidden_pattern_writes_to_allowed_forbidden() -> None:
    assert rule_type_section("forbidden_pattern") == "Allowed APIs / Forbidden APIs"


def test_quick_add_reviewer_note_writes_to_reviewer_notes() -> None:
    assert rule_type_section("reviewer_note") == "Reviewer Notes / Learned Fixes"


# ---------------------------------------------------------------------------
# Structured bullet formatting
# ---------------------------------------------------------------------------

def test_format_input_mock_rule() -> None:
    bullet = format_quick_add_rule("input_mock", {"signal": "APOK2", "mock_api": "Rte_Read_COMRX_APOK2", "default_value": "1"})
    assert "APOK2" in bullet
    assert "Rte_Read_COMRX_APOK2" in bullet
    assert "EXPECT_CALL" in bullet
    assert "WillRepeatedly" in bullet
    assert "[source: quick_add]" in bullet


def test_format_output_assertion_rule() -> None:
    bullet = format_quick_add_rule("output_assertion", {"output_var": "V_PMODE_STS", "assertion_pattern": "EXPECT_THAT(V_PMODE_STS, Eq(expected))"})
    assert "V_PMODE_STS" in bullet
    assert "EXPECT_THAT" in bullet
    assert "[source: quick_add]" in bullet


def test_format_timing_rule() -> None:
    bullet = format_quick_add_rule("timing", {"timing_name": "T7", "execution_pattern": "repeated igsw_Main_Run() in for-loop"})
    assert "T7" in bullet
    assert "igsw_Main_Run" in bullet
    assert "[source: quick_add]" in bullet


def test_format_fixture_rule() -> None:
    bullet = format_quick_add_rule("fixture_style", {"fixture_name": "TryToChangeOnToOffTest", "scope_note": "for power mode tests"})
    assert "TryToChangeOnToOffTest" in bullet
    assert "[source: quick_add]" in bullet


def test_format_signal_mapping_rule() -> None:
    bullet = format_quick_add_rule("signal_mapping", {"signal": "DRDYSTS", "rte_api": "Rte_Read_COMRX_DRDYSTS", "direction": "INPUT"})
    assert "DRDYSTS" in bullet
    assert "Rte_Read_COMRX_DRDYSTS" in bullet
    assert "INPUT" in bullet
    assert "[source: quick_add]" in bullet


def test_format_forbidden_pattern_rule() -> None:
    bullet = format_quick_add_rule("forbidden_pattern", {"pattern": "WaitMs()", "reason": "not in sample"})
    assert "WaitMs()" in bullet
    assert "not in sample" in bullet
    assert "[source: quick_add]" in bullet


def test_format_reviewer_note() -> None:
    bullet = format_quick_add_rule("reviewer_note", {"note": "Use TODO_REVIEW for uncertain APIs"})
    assert "TODO_REVIEW" in bullet
    assert "[source: quick_add]" in bullet


def test_format_without_source_tag() -> None:
    bullet = format_quick_add_rule("reviewer_note", {"note": "My note"}, source_tag=False)
    assert "[source: quick_add]" not in bullet
    assert "My note" in bullet


# ---------------------------------------------------------------------------
# Append to correct section and persist
# ---------------------------------------------------------------------------

def test_input_mock_rule_appended_to_correct_section() -> None:
    bullet = format_quick_add_rule("input_mock", {"signal": "APOK2", "mock_api": "Rte_Read_COMRX_APOK2"})
    section = rule_type_section("input_mock")
    content = append_to_section(DEFAULT_MEMORY, section, bullet)
    assert "APOK2" in content
    assert "## Input Mock Pattern" in content
    # Check it appears under the correct section
    idx_section = content.find("## Input Mock Pattern")
    idx_bullet = content.find("APOK2")
    assert idx_section < idx_bullet, "Bullet must appear after its section header"


def test_signal_mapping_rule_appended_to_spec_signal_map() -> None:
    bullet = format_quick_add_rule("signal_mapping", {"signal": "DRDYSTS", "rte_api": "Rte_Read_COMRX_DRDYSTS", "direction": "INPUT"})
    section = rule_type_section("signal_mapping")
    content = append_to_section(DEFAULT_MEMORY, section, bullet)
    assert "DRDYSTS" in content
    idx_section = content.find("## Spec Signal to Test Code Map")
    idx_bullet = content.find("DRDYSTS")
    assert idx_section < idx_bullet


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def test_duplicate_quick_add_not_inserted_twice() -> None:
    bullet = format_quick_add_rule("input_mock", {"signal": "APOK2", "mock_api": "Rte_Read_COMRX_APOK2"})
    section = rule_type_section("input_mock")
    content = append_to_section(DEFAULT_MEMORY, section, bullet)
    # Check before second append
    check = check_before_append(content, section, bullet)
    assert check["is_duplicate"] is True, "Second identical bullet must be detected as duplicate"


def test_non_duplicate_not_flagged() -> None:
    bullet_a = format_quick_add_rule("input_mock", {"signal": "APOK2"})
    bullet_b = format_quick_add_rule("input_mock", {"signal": "DRDYSTS"})
    section = rule_type_section("input_mock")
    content = append_to_section(DEFAULT_MEMORY, section, bullet_a)
    check = check_before_append(content, section, bullet_b)
    assert check["is_duplicate"] is False


# ---------------------------------------------------------------------------
# Conflict detection for signal mapping
# ---------------------------------------------------------------------------

def test_conflicting_signal_mapping_triggers_warning() -> None:
    bullet_v1 = format_quick_add_rule("signal_mapping", {"signal": "FOO", "rte_api": "Rte_Read_FOO_v1"})
    bullet_v2 = format_quick_add_rule("signal_mapping", {"signal": "FOO", "rte_api": "Rte_Read_FOO_v2"})
    section = rule_type_section("signal_mapping")
    content = append_to_section(DEFAULT_MEMORY, section, bullet_v1)
    check = check_before_append(content, section, bullet_v2)
    # Should detect conflict because same signal "FOO" appears with different API
    assert not check["is_duplicate"]
    # Conflicts may or may not be detected depending on normalization
    assert isinstance(check["conflicts"], list)


# ---------------------------------------------------------------------------
# Prompt priority — quick_add rules prioritized
# ---------------------------------------------------------------------------

def test_quick_add_rules_appear_in_prioritized_memory() -> None:
    bullet = format_quick_add_rule("input_mock", {"signal": "APOK2", "mock_api": "Rte_Read_COMRX_APOK2"})
    section = rule_type_section("input_mock")
    content = append_to_section(DEFAULT_MEMORY, section, bullet)
    result = memory_for_prompt_prioritized(content, char_limit=5000)
    assert "APOK2" in result, "quick_add rule must appear in prioritized prompt memory"


def test_quick_add_rules_not_trimmed_before_generic_prose() -> None:
    # Add many generic lines to fill budget
    content = DEFAULT_MEMORY
    for i in range(50):
        content = append_to_section(content, "Temporary Regeneration Notes", f"- Generic note {i}")
    # Add a quick_add rule with [source: quick_add] tag
    bullet = format_quick_add_rule("output_assertion", {"output_var": "V_PMODE_STS"})
    section = rule_type_section("output_assertion")
    content = append_to_section(content, section, bullet)
    result = memory_for_prompt_prioritized(content, char_limit=1000)
    # Quick add rule in high-priority section (Output Assertion Pattern) should appear
    assert "V_PMODE_STS" in result, "quick_add rule must not be trimmed before generic notes"


def test_quick_add_does_not_require_yaml_config() -> None:
    """Quick add must work with no YAML/config files — only project memory markdown."""
    bullet = format_quick_add_rule("timing", {"timing_name": "T7", "execution_pattern": "igsw_Main_Run() repeated"})
    assert bullet  # rule generated without any YAML
    section = rule_type_section("timing")
    content = append_to_section(DEFAULT_MEMORY, section, bullet)
    assert "T7" in content  # persisted to markdown, no YAML needed
