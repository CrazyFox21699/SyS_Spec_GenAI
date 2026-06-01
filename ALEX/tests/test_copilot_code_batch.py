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


def test_batch_includes_missing_io_in_copilot_request() -> None:
    bundle = _bundle_with_rows()
    gtest_state: dict = {"harness": {"fixture_class": "T"}, "drafts": {}}
    reply = (
        "```cpp\n"
        "// {cid}\n"
        "TEST_F(T,{cid}){{ EXPECT_EQ(1,1); }}\n"
        "```\n"
        "ASSUMPTIONS:\n- mocked response"
    )

    def fake_copilot(_cfg: dict, prompt: str, **_kwargs: object) -> dict:
        cid = "TC2" if "candidate_id=TC2" in prompt else "TC1"
        return {"ok": True, "reply": reply.format(cid=cid)}

    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        side_effect=fake_copilot,
    ) as chat:
        out = run_copilot_code_generate_batch(
            bundle,
            gtest_state,
            candidate_ids=["TC1", "TC2"],
            cfg={},
            persist_drafts=True,
        )
    assert chat.call_count == 2
    assert out["skipped"] == 0
    assert out["generated"] + out["needs_review"] + out["failed"] == 2
    assert gtest_state["drafts"].get("TC1")
    assert gtest_state["drafts"].get("TC2")
    assert [r["candidate_id"] for r in out["results"]] == ["TC1", "TC2"]
    assert all(not r.get("skipped") for r in out["results"])
