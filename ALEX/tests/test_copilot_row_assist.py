"""Tests for row-level Copilot assist."""

from __future__ import annotations

from unittest.mock import patch

from web.copilot_row_assist import write_from_row_via_copilot


def test_write_from_row_parses_draft() -> None:
    row = {
        "candidate_id": "TC1",
        "use_case": "old uc",
        "operation": "old op",
        "expected_input": "Given: A=1",
        "expected_output": "Then: B=0",
    }
    reply = (
        '{"candidate_id":"TC1","use_case":"new uc","operation":"new op",'
        '"expected_input":"Given: A=2","expected_output":"Then: B=1"}'
    )
    with patch(
        "web.copilot_row_assist.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        out = write_from_row_via_copilot({}, row)
    assert out["ok"] is True
    assert out["draft"]["use_case"] == "new uc"
    assert out["draft"]["expected_output"] == "Then: B=1"
