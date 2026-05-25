from __future__ import annotations

from web.reasoning_session import append_turn, create_session, load_session


def test_reasoning_session_persists_hashes_and_turns(tmp_path) -> None:
    bundle = {
        "logic_blocks": [{"id": "LB1", "name": "CTRL", "raw_expression": "A AND B"}],
        "test_candidates": [],
        "logic_review_items": [{"logic_id": "LB1", "control_name": "CTRL"}],
    }

    session = create_session(tmp_path, bundle, logic_id="LB1", engineer_note="A means active", provider="copilot")
    assert session["logic_id"] == "LB1"
    assert session["brief_hash"]
    assert session["evidence_hash"]

    updated = append_turn(tmp_path, logic_id="LB1", role="engineer", content="Please inspect branch 1")
    assert updated["turns"][0]["content"] == "Please inspect branch 1"

    loaded = load_session(tmp_path, "LB1")
    assert loaded["turns"][0]["role"] == "engineer"
