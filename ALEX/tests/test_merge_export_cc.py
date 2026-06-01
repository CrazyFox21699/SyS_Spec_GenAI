"""Merged export uses .cc filename."""

from __future__ import annotations

from web.code_text_transform import merge_export_filename, merge_saved_code_preview


def test_merge_export_filename_pattern() -> None:
    name = merge_export_filename("job-123")
    assert name.startswith("ALEX_GTest_job-123_")
    assert name.endswith(".cc")


def test_merge_requires_approval_when_flag_set() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "test_function": "f",
                "event": "e",
                "use_case_description": "g",
                "precondition": [],
                "operation": {"given": [], "when": []},
                "expectation": [{"description": "out"}],
                "status": "candidate",
            }
        ]
    }
    gtest_state = {
        "drafts": {
            "TC_A": {
                "code_status": "SAVED",
                "full_snippet": "// TC_A\nTEST_F(Fix, A) { EXPECT_TRUE(true); }",
                "code_body": "TEST_F(Fix, A) { EXPECT_TRUE(true); }",
            }
        }
    }
    sync_map = {"TC_A": "ok"}
    without = merge_saved_code_preview(
        gtest_state, bundle, sync_map=sync_map, require_engineer_approved=False, job_id="j1"
    )
    assert without["saved_count"] == 1
    with_req = merge_saved_code_preview(
        gtest_state, bundle, sync_map=sync_map, require_engineer_approved=True, job_id="j1"
    )
    assert with_req["saved_count"] == 0
    gtest_state["drafts"]["TC_A"]["engineer_approved"] = True
    approved = merge_saved_code_preview(
        gtest_state, bundle, sync_map=sync_map, require_engineer_approved=True, job_id="j1"
    )
    assert approved["saved_count"] == 1
    assert approved["export_filename"].endswith(".cc")
