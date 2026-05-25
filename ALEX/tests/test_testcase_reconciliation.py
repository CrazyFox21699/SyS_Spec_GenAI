from __future__ import annotations

from src.engine.testcase_reconciliation import build_reconciliation_plan


def test_reconciliation_plan_classifies_update_add_retire() -> None:
    bundle = {
        "test_candidates": [
            {"id": "TC1", "traceability": {"logic_block": "LB1"}},
            {"id": "TC2", "traceability": {"logic_block": "LB1"}},
            {"id": "OTHER", "traceability": {"logic_block": "LB2"}},
        ]
    }
    patches = [
        {"candidate_id": "TC1", "given": [{"signal": "A", "value": "1"}], "citations": [{"file": "spec.xlsx", "row": 4}]},
        {"given": [{"signal": "B", "value": "0"}], "citations": [{"file": "spec.xlsx", "row": 5}]},
        {"action": "retire", "candidate_id": "TC2", "citations": [{"candidate_id": "TC2"}]},
    ]

    plan = build_reconciliation_plan(bundle, "LB1", patches, provider="copilot")

    assert [row["action"] for row in plan["actions"]] == ["update_existing", "add_new", "retire"]
    assert plan["summary"]["update_existing"] == 1
    assert plan["summary"]["add_new"] == 1
    assert plan["summary"]["retire"] == 1


def test_reconciliation_plan_marks_unknown_retire_for_review() -> None:
    bundle = {"test_candidates": [{"id": "TC1", "traceability": {"logic_block": "LB1"}}]}

    plan = build_reconciliation_plan(
        bundle,
        "LB1",
        [{"action": "retire", "candidate_id": "MISSING", "citations": []}],
    )

    assert plan["actions"][0]["action"] == "needs_review"
    assert plan["actions"][0]["review_required"] is True
