"""API-level tests for gtest workspace persistence."""

from __future__ import annotations

import json
from pathlib import Path

from web.gtest_workspace import (
    bulk_delete_code,
    bulk_regen_comments,
    classify_sync_status,
    export_library_preset,
    generate_draft_for_request,
    import_library_preset,
    load_gtest_state,
    regen_comment_only_draft,
    save_draft,
    save_gtest_state,
)


def test_gtest_state_roundtrip(tmp_path: Path) -> None:
    state = {
        "harness": {"fixture_class": "MyFixture"},
        "code_variable_map": {"SIG_A": "in.SIG_A"},
        "drafts": {},
    }
    save_gtest_state(tmp_path, state)
    loaded = load_gtest_state(tmp_path)
    assert loaded["harness"]["fixture_class"] == "MyFixture"
    assert loaded["code_variable_map"]["SIG_A"] == "in.SIG_A"
    assert (tmp_path / "bundle" / "gtest.json").exists()


def test_generate_and_save_draft() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_PM_001",
                "event": "Shutdown",
                "operation": {
                    "given": [{"signal": "IGN_SW", "value": "0"}],
                    "when": [{"timing": "elapsed_time >= 50 ms"}],
                },
                "expectation": [{"signal": "Mode_STS", "value": "0"}],
                "traceability": {},
            }
        ],
        "logic_blocks": [],
        "signals": [],
    }
    gtest_state = {
        "harness": {},
        "code_variable_map": {"IGN_SW": "in.IGN_SW", "Mode_STS": "out.Mode_STS"},
        "drafts": {},
    }
    draft = generate_draft_for_request(bundle, gtest_state, candidate_id="TC_PM_001")
    assert "TEST_F" in draft["code_body"]
    gtest_state = save_draft(gtest_state, draft_key="TC_PM_001", draft=draft)
    assert "TC_PM_001" in gtest_state["drafts"]


def test_library_preset_import_export() -> None:
    state = {"harness": {"fixture_class": "A"}, "code_variable_map": {"X": "in.X"}, "drafts": {}}
    preset = export_library_preset(state)
    merged = import_library_preset({"harness": {}, "code_variable_map": {}, "drafts": {}}, preset)
    assert merged["code_variable_map"]["X"] == "in.X"
    assert merged["harness"]["fixture_class"] == "A"


def _sample_bundle() -> dict:
    return {
        "test_candidates": [
            {
                "id": "TC_PM_001",
                "event": "Shutdown",
                "operation": {
                    "given": [{"signal": "IGN_SW", "value": "0"}],
                    "when": [{"timing": "elapsed_time >= 50 ms"}],
                },
                "expectation": [{"signal": "Mode_STS", "value": "0"}],
                "traceability": {},
            }
        ],
        "logic_blocks": [],
        "signals": [],
        "ai_assists": {"candidate_overlays": {}},
    }


def test_classify_sync_status_no_code() -> None:
    bundle = _sample_bundle()
    gtest_state = {"drafts": {}, "harness": {}, "code_variable_map": {}}
    sync = classify_sync_status(bundle, gtest_state)
    assert sync["summary"]["no_code"] == 1
    assert sync["rows"][0]["status"] == "no_code"


def test_regen_comment_only_keeps_test_body() -> None:
    bundle = _sample_bundle()
    gtest_state = {
        "harness": {},
        "code_variable_map": {"IGN_SW": "in.IGN_SW", "Mode_STS": "out.Mode_STS"},
        "drafts": {},
    }
    draft = generate_draft_for_request(bundle, gtest_state, candidate_id="TC_PM_001")
    gtest_state = save_draft(gtest_state, draft_key="TC_PM_001", draft=draft)
    original_body = gtest_state["drafts"]["TC_PM_001"]["code_body"]
    out = regen_comment_only_draft(bundle, gtest_state, "TC_PM_001")
    assert out["ok"] is True
    updated = gtest_state["drafts"]["TC_PM_001"]
    assert updated["code_body"] == original_body
    assert "// @alex:begin TC_PM_001" in updated["full_snippet"]


def test_bulk_regen_comments_stale_only() -> None:
    bundle = _sample_bundle()
    gtest_state = {
        "harness": {},
        "code_variable_map": {"IGN_SW": "in.IGN_SW", "Mode_STS": "out.Mode_STS"},
        "drafts": {},
    }
    draft = generate_draft_for_request(bundle, gtest_state, candidate_id="TC_PM_001")
    draft["spec_hash"] = "stale_hash"
    gtest_state = save_draft(gtest_state, draft_key="TC_PM_001", draft=draft)
    out = bulk_regen_comments(bundle, gtest_state, ["TC_PM_001"], stale_only=True)
    assert out["regenerated"] == 0
    sync = classify_sync_status(bundle, gtest_state)
    stale = [r for r in sync["rows"] if r["status"] == "stale_body"]
    assert len(stale) == 1


def test_bulk_delete_code() -> None:
    state = {"drafts": {"TC1": {"full_snippet": "x"}}, "tc_code_index": {"TC1": {}}}
    out = bulk_delete_code(state, ["TC1"])
    assert out["count"] == 1
    assert "TC1" not in state["drafts"]
