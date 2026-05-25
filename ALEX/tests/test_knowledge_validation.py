"""Validation loop after knowledge patches."""

from web.knowledge_validation import apply_patches_with_validation, compliance_snapshot


def test_apply_patches_marks_review_required_on_logic_fail() -> None:
    bundle = {
        "logic_blocks": [
            {
                "id": "LB1",
                "name": "OUT",
                "raw_expression": "OUT",
                "tree": {"type": "signal_condition", "signal": "A", "operator": "==", "value": "1"},
            }
        ],
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1", "logic_branch": "branch_1"},
                "operation": {"given": []},
            }
        ],
    }
    patches = [{"candidate_id": "TC1", "given": []}]
    apply_patches_with_validation(bundle, "LB1", patches, source="test")
    assert bundle["test_candidates"][0].get("review_status") == "review_required"
    snap = compliance_snapshot(bundle, "LB1")
    assert snap[0]["candidate_id"] == "TC1"
