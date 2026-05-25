"""Tests for project memory merge and IO remember."""

from __future__ import annotations

from web.project_memory import merge_project_memory, remember_io_from_text, save_bundle_memory


def test_remember_io_from_text() -> None:
    memory = {"io_variable_map": {}}
    updated = remember_io_from_text(
        memory,
        expected_input="Given: OK_SHUTOFF=1",
        expected_output="Then: DECISION=1",
    )
    assert updated["OK_SHUTOFF"] == "in.OK_SHUTOFF"
    assert updated["DECISION"] == "out.DECISION"


def test_save_bundle_memory_roundtrip() -> None:
    bundle: dict = {"ai_assists": {}}
    mem = {"io_variable_map": {"A": "in.A"}, "signal_roles": {}, "shared_preconditions": [], "verification_patterns": []}
    save_bundle_memory(bundle, mem)
    merged = merge_project_memory(bundle=bundle)
    assert merged["io_variable_map"]["A"] == "in.A"
