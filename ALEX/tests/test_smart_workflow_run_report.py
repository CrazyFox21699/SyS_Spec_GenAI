"""Smart workflow run report aggregation."""

from __future__ import annotations

from pathlib import Path

from web.test_code_smart_workflow import (
    build_smart_workflow_run_report,
    format_smart_workflow_run_report_markdown,
    record_smart_workflow_run,
)


def test_run_report_counts_and_markdown(tmp_path: Path) -> None:
    bundle = {
        "test_candidates": [
            {
                "candidate_id": "TC_001",
                "expected_input": "Given: WMODE_CMD = 1",
                "expected_output": "Then: V_PMODE_STS = 1",
            }
        ],
    }
    gtest_state = {
        "drafts": {
            "TC_001": {
                "code_status": "SAVED",
                "test_name": "DupTest",
                "quality_results": [
                    {"name": "unknown_api", "severity": "WARNING", "message": "API not in catalog or sample: foo()"},
                ],
            },
            "TC_002": {
                "code_status": "NEEDS_REVIEW",
                "test_name": "DupTest",
            },
        },
        "mapping_coverage": {
            "ready_for_local_generation": 0,
            "missing_mapping_count": 1,
            "top_missing_terms": ["WMODE_CMD"],
            "detected_mapping_count": 2,
        },
        "mapping_proposals": {
            "proposals": [
                {"signal": "WMODE_CMD", "proposed_code": "EXPECT_CALL(...)", "confidence": 0.7},
            ],
        },
    }
    record_smart_workflow_run(
        gtest_state,
        "smart_generate",
        {"steps": ["auto_accepted_1"], "batch_summary": {"saved": 1}},
    )
    record_smart_workflow_run(
        gtest_state,
        "analyze_project_context",
        {
            "fixture_inferred": "RteDefaultAction",
            "apis_inferred": 3,
            "mapping_keys_inferred": 5,
            "summary": "Inferred 5 mapping keys",
        },
    )

    report = build_smart_workflow_run_report(bundle, gtest_state, tmp_path, language="EN")
    assert report["total_testcase_count"] >= 1
    assert report["fixture_detected"] == "RteDefaultAction"
    assert report["generated_saved_count"] == 1
    assert report["needs_review_count"] == 1
    assert report["mappings_requiring_review_count"] == 1
    assert report["auto_accepted_mapping_count"] >= 1
    assert "WMODE_CMD" in (report.get("top_missing_signals") or [])
    assert len(report.get("duplicate_test_names") or []) == 1
    md = format_smart_workflow_run_report_markdown(report, job_id="job_test")
    assert "# ALEX Smart Workflow Run Report" in md
    assert "WMODE_CMD" in md
