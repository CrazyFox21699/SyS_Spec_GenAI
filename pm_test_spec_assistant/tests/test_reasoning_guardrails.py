from __future__ import annotations

from web.reasoning_guardrails import validate_reasoning_hypothesis
from web.reasoning_session import append_hypothesis


def test_reasoning_hypothesis_requires_citations() -> None:
    payload = {
        "logic_id": "LB1",
        "review_required": True,
        "claims": [{"claim": "A means active", "citations": []}],
        "open_questions": [],
        "testcase_patch_plan": [],
    }

    out = validate_reasoning_hypothesis(payload, logic_id="LB1")

    assert out["ok"] is False
    assert "missing evidence citations" in out["errors"][0]


def test_reasoning_hypothesis_accepts_cited_patch(tmp_path) -> None:
    payload = {
        "logic_id": "LB1",
        "review_required": True,
        "claims": [{"claim": "A means active", "citations": [{"file": "spec.xlsx", "row": 3}]}],
        "open_questions": [],
        "testcase_patch_plan": [
            {
                "action": "update_existing",
                "candidate_id": "TC1",
                "given": [{"signal": "A", "value": "1"}],
                "citations": [{"candidate_id": "TC1"}, {"file": "spec.xlsx", "row": 3}],
            }
        ],
    }

    out = validate_reasoning_hypothesis(payload, logic_id="LB1")
    session = append_hypothesis(tmp_path, logic_id="LB1", hypothesis=payload, provider="copilot")

    assert out["ok"] is True
    assert session["hypotheses"][0]["validation"]["ok"] is True
