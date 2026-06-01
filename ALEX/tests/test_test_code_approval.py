"""Test code approval workflow."""

from __future__ import annotations

from web.test_code_approval import (
    approve_all_saved_test_code,
    approve_test_code_drafts,
    count_workflow_statuses,
    reopen_test_code_drafts,
)


def test_approve_saved_and_merge_gate() -> None:
    gtest_state = {
        "drafts": {
            "TC_A": {"code_status": "SAVED", "full_snippet": "TEST_F(F, A) {}"},
            "TC_B": {"code_status": "NEEDS_REVIEW", "full_snippet": "TEST_F(F, B) {}"},
        }
    }
    r = approve_test_code_drafts(gtest_state, ["TC_A", "TC_B"], only_saved=True)
    assert r["approved"] == ["TC_A"]
    assert gtest_state["drafts"]["TC_A"]["engineer_approved"] is True
    counts = count_workflow_statuses(gtest_state)
    assert counts["APPROVED"] == 1
    reopen_test_code_drafts(gtest_state, ["TC_A"])
    assert "engineer_approved" not in gtest_state["drafts"]["TC_A"]


def test_approve_all_saved() -> None:
    gtest_state = {
        "drafts": {
            "TC_A": {"code_status": "SAVED", "full_snippet": "x"},
            "TC_C": {"code_status": "SAVED", "full_snippet": "y"},
        }
    }
    r = approve_all_saved_test_code(gtest_state)
    assert r["approved_count"] == 2
