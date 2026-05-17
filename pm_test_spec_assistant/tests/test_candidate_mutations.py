from __future__ import annotations

import pytest

from web.candidate_mutations import (
    clone_candidate,
    create_blank_candidate,
    soft_delete_candidate,
)


def test_create_and_clone_candidate() -> None:
    bundle: dict = {"test_candidates": [{"id": "TC_PM_001", "source": "deterministic_candidate_generator"}]}
    created = create_blank_candidate(bundle, logic_id="LB_01", control_name="TestCtrl")
    assert created["id"].startswith("TC_ENG_")
    assert created["source"] == "engineer_manual"

    cloned = clone_candidate(bundle, "TC_PM_001", logic_id="LB_01")
    assert cloned["id"] != "TC_PM_001"
    assert cloned["parent_id"] == "TC_PM_001"
    assert cloned["source"] == "engineer_clone"
    assert len(bundle["test_candidates"]) == 3


def test_soft_delete_only_engineer_rows() -> None:
    bundle: dict = {
        "test_candidates": [
            {"id": "TC_ENG_001", "source": "engineer_manual", "status": "candidate"},
            {"id": "TC_PM_001", "source": "deterministic_candidate_generator", "status": "candidate"},
        ]
    }
    soft_delete_candidate(bundle, "TC_ENG_001")
    assert bundle["test_candidates"][0]["status"] == "removed"
    with pytest.raises(ValueError):
        soft_delete_candidate(bundle, "TC_PM_001")
