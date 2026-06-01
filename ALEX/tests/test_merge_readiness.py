"""Merge preview includes quality readiness counts."""

from __future__ import annotations

from web.code_text_transform import merge_saved_code_preview


def test_merge_readiness_warns_on_saved_warning() -> None:
    gtest_state = {
        "drafts": {
            "TC_A": {
                "code_status": "SAVED",
                "full_snippet": "// TC_A\nTEST_F(F, TC_A) { EXPECT_EQ(1, 1); }",
                "quality_summary": "WARNING",
                "review_reason": "missing timing",
            },
        }
    }
    bundle = {
        "test_candidates": [{"id": "TC_A", "no": 1}],
        "ai_assists": {"candidate_overlays": {}},
    }
    out = merge_saved_code_preview(gtest_state, bundle, sync_map={"TC_A": "ok"})
    mr = out.get("merge_readiness") or {}
    assert mr.get("saved_quality_warning") == 1
    assert any("WARNING" in w for w in out.get("warnings") or [])
