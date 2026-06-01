"""Batch target resolution respects import groups and Excel order."""

from __future__ import annotations

from web.batch_target_resolution import (
    import_group_key,
    resolve_batch_targets,
    sort_candidate_ids_by_preview_order,
)


def _tc(cid: str, group: str) -> dict:
    return {
        "id": cid,
        "test_group": group,
        "test_function": "fn",
        "event": "ev",
        "use_case_description": group,
        "precondition": [],
        "operation": {"given": [{"description": f"in {cid}"}], "when": []},
        "expectation": [{"description": f"out {cid}"}],
        "status": "candidate",
    }


def _bundle() -> dict:
    return {
        "test_candidates": [
            _tc("TC_C", "GRP_A"),
            _tc("TC_A", "GRP_A"),
            _tc("TC_B", "GRP_B"),
        ],
    }


def test_group_scope_only_same_test_group() -> None:
    bundle = _bundle()
    gtest_state: dict = {"drafts": {}}
    resolved = resolve_batch_targets(
        bundle,
        gtest_state,
        scope="group",
        group_key="GRP_A",
        group_field="test_group",
    )
    assert resolved["ok"] is True
    assert resolved["candidate_ids"] == ["TC_C", "TC_A"]


def test_filter_scope_uses_client_candidate_ids_in_import_order() -> None:
    bundle = _bundle()
    gtest_state: dict = {"drafts": {}}
    resolved = resolve_batch_targets(
        bundle,
        gtest_state,
        scope="filter",
        candidate_ids=["TC_A", "TC_C", "TC_B"],
    )
    assert resolved["candidate_ids"] == ["TC_C", "TC_A", "TC_B"]


def test_selected_scope_requires_explicit_ids() -> None:
    bundle = _bundle()
    gtest_state: dict = {"drafts": {}}
    resolved = resolve_batch_targets(bundle, gtest_state, scope="selected", candidate_ids=[])
    assert resolved["ok"] is False
    resolved2 = resolve_batch_targets(
        bundle, gtest_state, scope="selected", candidate_ids=["TC_B"]
    )
    assert resolved2["candidate_ids"] == ["TC_B"]


def test_sort_preserves_preview_order() -> None:
    rows = [
        {"candidate_id": "TC_C"},
        {"candidate_id": "TC_A"},
        {"candidate_id": "TC_B"},
    ]
    assert sort_candidate_ids_by_preview_order(["TC_B", "TC_A", "TC_C"], rows) == [
        "TC_C",
        "TC_A",
        "TC_B",
    ]


def test_import_group_key_from_row() -> None:
    assert import_group_key({"test_group": " Shutoff "}) == "Shutoff"


def test_all_scope_every_imported_testcase() -> None:
    bundle = _bundle()
    gtest_state: dict = {"drafts": {}}
    resolved = resolve_batch_targets(bundle, gtest_state, scope="all")
    assert resolved["ok"] is True
    assert set(resolved["candidate_ids"]) == {"TC_C", "TC_A", "TC_B"}
