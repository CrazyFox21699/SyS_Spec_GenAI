"""Tests for knowledge patch schema validation."""

from web.knowledge_patch_validation import validate_knowledge_patches


def _bundle():
    return {
        "test_candidates": [
            {
                "id": "TC_001",
                "review_status": "draft",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "0"}]},
            },
            {
                "id": "TC_002",
                "review_status": "approved",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": []},
            },
        ],
        "logic_blocks": [{"id": "LB1"}],
    }


def test_rejects_unknown_candidate_id():
    bundle = _bundle()
    patches = [{"candidate_id": "TC_999", "given": [{"signal": "A", "value": "1"}]}]
    out = validate_knowledge_patches(patches, bundle, "LB1", {})
    assert out["ok"] is False
    assert any("unknown candidate_id" in e for e in out["errors"])


def test_rejects_approved_candidate():
    bundle = _bundle()
    patches = [{"candidate_id": "TC_002", "given": [{"signal": "A", "value": "1"}]}]
    out = validate_knowledge_patches(patches, bundle, "LB1", {})
    assert out["ok"] is False
    assert any("approved" in e for e in out["errors"])


def test_accepts_valid_patch():
    bundle = _bundle()
    patches = [{"candidate_id": "TC_001", "given": [{"signal": "A", "value": "1"}]}]
    out = validate_knowledge_patches(patches, bundle, "LB1", {})
    assert out["ok"] is True
    assert len(out["valid_patches"]) == 1


def test_rejects_duplicate_signal_in_given():
    bundle = _bundle()
    patches = [
        {
            "candidate_id": "TC_001",
            "given": [{"signal": "A", "value": "1"}, {"signal": "A", "value": "2"}],
        }
    ]
    out = validate_knowledge_patches(patches, bundle, "LB1", {})
    assert out["ok"] is False
    assert any("duplicate signal" in e for e in out["errors"])
