"""API-level tests for gtest workspace persistence."""

from __future__ import annotations

import json
from pathlib import Path

from web.gtest_workspace import (
    export_library_preset,
    generate_draft_for_request,
    import_library_preset,
    load_gtest_state,
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
