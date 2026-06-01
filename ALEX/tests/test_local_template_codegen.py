"""Tests for mapping coverage and local template batch helpers."""

from __future__ import annotations

from pathlib import Path

from web.local_template_codegen import check_candidate_mapping, check_mapping_coverage
from web.project_code_config import load_project_code_config


def _mini_bundle() -> dict:
    return {
        "test_candidates": [
            {"id": "TC_PM_001", "no": 1, "event": "evt", "status": "candidate"},
            {"id": "TC_PM_002", "no": 2, "event": "evt2", "status": "candidate"},
        ],
        "ai_assists": {
            "candidate_overlays": {
                "TC_PM_001": {
                    "en": {
                        "expected_input": "Given: SIG_A = 1",
                        "expected_output": "Then: SIG_B = 0",
                    }
                },
                "TC_PM_002": {
                    "en": {
                        "expected_input": "Given: UNMAPPED = 1",
                        "expected_output": "Then: SIG_B = 0",
                    }
                },
            }
        },
    }


def test_check_candidate_mapping_ready(tmp_path: Path) -> None:
    config = load_project_code_config(tmp_path)
    gtest_state = {"code_variable_map": {"SIG_A": "h.SetA", "SIG_B": "EXPECT_EQ(h.GetB(), 0)"}}
    bundle = _mini_bundle()
    one = check_candidate_mapping(bundle, gtest_state, "TC_PM_001", config=config)
    assert one["ready"] is True


def test_check_mapping_coverage_counts(tmp_path: Path) -> None:
    gtest_state = {"code_variable_map": {"SIG_A": "x", "SIG_B": "y"}}
    bundle = _mini_bundle()
    result = check_mapping_coverage(bundle, gtest_state, tmp_path, language="EN")
    assert result["total_testcase_count"] == 2
    assert result["missing_mapping_count"] >= 1
    assert "TC_PM_002" in (result.get("affected_testcase_ids") or [])
