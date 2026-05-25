"""Tests for knowledge reconciliation preview/confirm flow."""

from __future__ import annotations

from web.knowledge_reconciliation import (
    build_patch_diffs,
    confirm_pending_knowledge,
    get_knowledge_apply_payload,
    reject_pending_knowledge,
    store_pending_knowledge_apply,
)


def _sample_bundle():
    return {
        "test_candidates": [
            {
                "id": "TC_001",
                "candidate_id": "TC_001",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "OK_SHUTOFF", "value": "TRUE"}]},
            }
        ],
        "logic_blocks": [{"id": "LB1", "name": "Shutoff"}],
    }


def test_store_pending_does_not_mutate_candidates():
    bundle = _sample_bundle()
    patches = [
        {
            "candidate_id": "TC_001",
            "action": "update_existing",
            "given": [{"signal": "OK_SHUTOFF", "value": "FALSE"}],
        }
    ]
    out = store_pending_knowledge_apply(bundle, "LB1", patches, provider="test")
    assert out["preview"] is True
    assert out["pending_patches"] == 1
    given = bundle["test_candidates"][0]["operation"]["given"]
    assert given[0]["value"] == "TRUE"


def test_build_patch_diffs_shows_before_after():
    bundle = _sample_bundle()
    patches = [
        {
            "candidate_id": "TC_001",
            "given": [{"signal": "OK_SHUTOFF", "value": "FALSE"}],
        }
    ]
    diffs = build_patch_diffs(bundle, "LB1", patches)
    assert len(diffs) == 1
    assert "OK_SHUTOFF" in diffs[0]["before_expected_input"]
    assert diffs[0]["after_expected_input"]
    assert "logic_comply" in diffs[0]
    assert "default_selected" in diffs[0]


def test_confirm_applies_selected_patches():
    bundle = _sample_bundle()
    patches = [
        {
            "candidate_id": "TC_001",
            "action": "update_existing",
            "given": [{"signal": "SPEED", "value": "10"}],
        }
    ]
    store_pending_knowledge_apply(bundle, "LB1", patches, provider="test")
    result = confirm_pending_knowledge(bundle, "LB1", [0], {})
    assert result["ok"] is True
    assert result["applied_patch_count"] == 1
    payload = get_knowledge_apply_payload(bundle, "LB1")
    assert payload["status"] == "applied"


def test_reject_clears_pending():
    bundle = _sample_bundle()
    store_pending_knowledge_apply(
        bundle,
        "LB1",
        [{"candidate_id": "TC_001", "given": [{"signal": "A", "value": "1"}]}],
        provider="test",
    )
    out = reject_pending_knowledge(bundle, "LB1")
    assert out["status"] == "rejected"
    payload = get_knowledge_apply_payload(bundle, "LB1")
    assert payload["status"] == "rejected"
    assert payload["patches"] == []
