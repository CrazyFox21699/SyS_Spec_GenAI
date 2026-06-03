"""Tests for project_testcode_memory — global memory, extraction, section append, prompt injection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from web.project_testcode_memory import (
    DEFAULT_MEMORY,
    SECTIONS,
    append_to_section,
    build_proposed_memory,
    extract_patterns_from_sample,
    load_global_memory,
    load_memory_for_job,
    memory_for_prompt,
    merge_proposed_into_memory,
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
    assert "Project Test Code Memory" in prompt
    assert "PowerModeTest fixture" in prompt


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
