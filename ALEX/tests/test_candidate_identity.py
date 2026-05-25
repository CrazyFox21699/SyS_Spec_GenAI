"""Tests for candidate identity update and rename."""

from __future__ import annotations

import pytest

from web.candidate_mutations import update_candidate_identity


def _bundle_with_candidate(cid: str = "TC_OLD") -> dict:
    return {
        "test_candidates": [
            {
                "id": cid,
                "test_function": "Power",
                "event": "evt",
                "use_case_description": "x",
                "operation": {"given": [], "when": []},
                "expectation": [],
            }
        ],
        "ai_assists": {
            "candidate_overlays": {
                cid: {"en": {"use_case": "u"}, "changed_fields": ["UseCase"]},
            }
        },
    }


def test_rename_candidate_moves_overlay() -> None:
    bundle = _bundle_with_candidate("TC_OLD")
    gtest = {"drafts": {"TC_OLD": {"full_snippet": "// x"}}}
    out = update_candidate_identity(
        bundle,
        "TC_OLD",
        new_candidate_id="TC_NEW",
        gtest_state=gtest,
    )
    assert out["candidate_id"] == "TC_NEW"
    assert bundle["test_candidates"][0]["id"] == "TC_NEW"
    assert "TC_NEW" in bundle["ai_assists"]["candidate_overlays"]
    assert "TC_OLD" not in bundle["ai_assists"]["candidate_overlays"]
    assert "TC_NEW" in gtest["drafts"]


def test_rename_duplicate_rejected() -> None:
    bundle = {
        "test_candidates": [{"id": "A"}, {"id": "B"}],
        "ai_assists": {},
    }
    with pytest.raises(ValueError, match="already exists"):
        update_candidate_identity(bundle, "A", new_candidate_id="B")


def test_update_test_function_event() -> None:
    bundle = _bundle_with_candidate()
    out = update_candidate_identity(
        bundle,
        "TC_OLD",
        test_function="New fn",
        event="New evt",
    )
    cand = out["candidate"]
    assert cand["test_function"] == "New fn"
    assert cand["event"] == "New evt"
