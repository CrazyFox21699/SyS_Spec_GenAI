"""Verify that POST /api/review/testcode-confirm-selected is registered.

If the route-registration tests fail it means main.py lost the route and the UI will
show 'Confirm API endpoint not found' or 'Confirm selected failed: Not Found'.
"""

from __future__ import annotations


# --------------------------------------------------------------------------- #
# Route-registration check (no server / no test data needed)
# --------------------------------------------------------------------------- #

CONFIRM_SELECTED_PATH = "/api/review/testcode-confirm-selected"
SINGLE_CONFIRM_APPROVE_PATH = "/api/review/testcode-approve"


def _registered_post_paths() -> set[str]:
    from web.main import app
    return {
        r.path
        for r in app.routes
        if hasattr(r, "methods") and "POST" in r.methods and hasattr(r, "path")
    }


def test_confirm_selected_route_registered() -> None:
    paths = _registered_post_paths()
    assert CONFIRM_SELECTED_PATH in paths, (
        f"POST {CONFIRM_SELECTED_PATH} is not registered. "
        "Single confirm and Confirm selected will both return 404. "
        f"Registered POST routes: {sorted(paths)}"
    )


def test_testcode_approve_route_still_registered() -> None:
    """Old approve route must remain so existing callers are not broken."""
    paths = _registered_post_paths()
    assert SINGLE_CONFIRM_APPROVE_PATH in paths, (
        f"POST {SINGLE_CONFIRM_APPROVE_PATH} is missing — may break legacy callers."
    )


# --------------------------------------------------------------------------- #
# confirm_test_code_drafts logic tests (no HTTP / no auth needed)
# --------------------------------------------------------------------------- #

def _make_gtest_state(drafts: dict) -> dict:
    return {"drafts": drafts}


def test_confirm_selected_confirms_non_empty_draft() -> None:
    from web.test_code_approval import confirm_test_code_drafts

    state = _make_gtest_state({
        "TC_001": {
            "full_snippet": "TEST_F(Fix, TC_001) { EXPECT_TRUE(true); }",
            "code_status": "NEEDS_REVIEW",
        }
    })
    result = confirm_test_code_drafts(state, ["TC_001"])
    assert result["confirmed_count"] == 1
    assert "TC_001" in result["confirmed"]
    assert result["skipped_empty_code"] == []
    assert result["selected_count"] == 1
    draft = state["drafts"]["TC_001"]
    assert draft["approval_status"] == "CONFIRMED"
    assert draft["exportable"] is True
    assert draft["engineer_approved"] is True


def test_confirm_selected_skips_empty_code() -> None:
    from web.test_code_approval import confirm_test_code_drafts

    state = _make_gtest_state({
        "TC_001": {"full_snippet": "", "code_body": "", "code_status": "NEEDS_REVIEW"}
    })
    result = confirm_test_code_drafts(state, ["TC_001"])
    assert result["confirmed_count"] == 0
    assert "TC_001" in result["skipped_empty_code"]


def test_confirm_selected_skips_missing_draft() -> None:
    from web.test_code_approval import confirm_test_code_drafts

    state = _make_gtest_state({})
    result = confirm_test_code_drafts(state, ["TC_GHOST"])
    assert result["confirmed_count"] == 0
    assert "TC_GHOST" in result["skipped_no_draft"]


def test_confirm_selected_needs_review_draft_confirmable() -> None:
    """NEEDS_REVIEW draft with non-empty code must confirm — quality gate does not block."""
    from web.test_code_approval import confirm_test_code_drafts

    state = _make_gtest_state({
        "TC_002": {
            "code_body": "TEST_F(Fix, TC_002) { /* ALEX_REVIEW: check output */ }",
            "code_status": "NEEDS_REVIEW",
        }
    })
    result = confirm_test_code_drafts(state, ["TC_002"])
    assert result["confirmed_count"] == 1, (
        f"NEEDS_REVIEW draft must be confirmable, got: {result}"
    )
    assert state["drafts"]["TC_002"]["exportable"] is True
