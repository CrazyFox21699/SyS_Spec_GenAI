"""Tests for Copilot GTest batch orchestrator."""

from __future__ import annotations

from unittest.mock import patch

from web.copilot_code_orchestrator import run_copilot_code_generate_batch


def _bundle_with_rows() -> dict:
    return {
        "test_candidates": [
            {
                "id": "TC1",
                "logic_id": "L1",
                "review_status": "ready",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
            {"id": "TC2", "logic_id": "L1", "review_status": "ready"},
        ],
        "logic_blocks": [{"logic_id": "L1", "control_name": "X", "raw_expression": "A"}],
        "ai_assists": {
            "workbook_overlays": {
                "TC1": {
                    "expected_input": "Given: A=1",
                    "expected_output": "Then: B=0",
                },
                "TC2": {},
            }
        },
    }


def test_batch_skips_missing_io() -> None:
    bundle = _bundle_with_rows()
    gtest_state: dict = {"harness": {"fixture_class": "T"}, "drafts": {}}
    reply = '{"test_name": "t", "code_body": "TEST_F(T,t){ EXPECT_EQ(1,1); }", "full_snippet": "TEST_F(T,t){ EXPECT_EQ(1,1); }"}'
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        out = run_copilot_code_generate_batch(
            bundle,
            gtest_state,
            candidate_ids=["TC1", "TC2"],
            cfg={},
            persist_drafts=True,
        )
    assert out["generated"] == 1
    assert out["skipped"] == 1
    assert gtest_state["drafts"].get("TC1")
