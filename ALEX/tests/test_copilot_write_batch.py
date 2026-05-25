"""Tests for Copilot write batching and NO-OP retry."""

from __future__ import annotations

from unittest.mock import patch

from web.copilot_orchestrator import run_write
from web.copilot_writer import chunk_plan_items, write_batch_size, write_drafts_via_m365
from web.project_memory import promote_verification_pattern


def test_chunk_plan_items_splits_batches() -> None:
    plan = {"plan_items": [{"plan_item_id": f"P{i}"} for i in range(10)]}
    chunks = chunk_plan_items(plan, 6)
    assert len(chunks) == 2
    assert len(chunks[0]) == 6
    assert len(chunks[1]) == 4


def test_write_drafts_batches_merge(monkeypatch) -> None:
    calls: list[int] = []

    def fake_write(cfg, context_pack, plan_slice, *, retry_notes=None):
        calls.append(len(plan_slice.get("plan_items") or []))
        return {
            "ok": True,
            "drafts": [
                {
                    "plan_item_id": row.get("plan_item_id"),
                    "action": "update_existing",
                    "candidate_id": row.get("plan_item_id"),
                    "use_case": "u",
                    "expected_input": "Given: A=1",
                    "expected_output": "Then: B=0",
                }
                for row in plan_slice.get("plan_items") or []
            ],
        }

    monkeypatch.setattr("web.copilot_writer._write_plan_slice", fake_write)
    plan = {"plan_items": [{"plan_item_id": f"P{i}", "candidate_id": f"TC{i}"} for i in range(8)]}
    out = write_drafts_via_m365({}, {"testcases": []}, plan, batch_size=3)
    assert out["ok"] is True
    assert len(out["drafts"]) == 8
    assert out["batch_count"] == 3
    assert calls == [3, 3, 2]


def test_promote_verification_pattern_dedupes() -> None:
    memory = {"verification_patterns": []}
    row = promote_verification_pattern(
        memory,
        logic_id="LB1",
        given_fingerprint="A=1",
        then_signals=["OUT"],
        candidate_ids=["TC1"],
        label="Test",
    )
    assert row["id"].startswith("VP_")
    promote_verification_pattern(
        memory,
        logic_id="LB1",
        given_fingerprint="A=1",
        then_signals=["OUT2"],
        candidate_ids=["TC2"],
    )
    assert len(memory["verification_patterns"]) == 1
    assert "TC2" in memory["verification_patterns"][0]["example_candidate_ids"]


def test_run_write_retries_noop(monkeypatch) -> None:
    bundle = {
        "logic_blocks": [{"id": "LB1", "name": "CTRL"}],
        "test_candidates": [
            {
                "id": "TC1",
                "status": "candidate",
                "traceability": {"logic_block": "LB1"},
                "use_case_description": "Same",
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}]},
            }
        ],
        "ai_assists": {
            "copilot_sessions": {
                "LB1": {
                    "context_pack": {"testcases": [{"candidate_id": "TC1", "use_case": "Same"}], "logic_id": "LB1"},
                    "plan": {
                        "plan_items": [
                            {
                                "plan_item_id": "P1",
                                "action": "update_existing",
                                "candidate_id": "TC1",
                            }
                        ]
                    },
                }
            },
            "candidate_overlays": {
                "TC1": {
                    "logic_id": "LB1",
                    "en": {
                        "use_case": "Same",
                        "expected_input": "Given: A=1",
                        "expected_output": "Then: B=0",
                    },
                    "changed_fields": ["UseCase", "ExpectedInput", "ExpectedOutput"],
                }
            },
        },
    }
    call_count = {"n": 0}

    def fake_write(cfg, pack, plan, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "ok": True,
                "drafts": [
                    {
                        "plan_item_id": "P1",
                        "action": "update_existing",
                        "candidate_id": "TC1",
                        "use_case": "Same",
                        "expected_input": "Given: A=1",
                        "expected_output": "Then: B=0",
                    }
                ],
                "batch_count": 1,
            }
        return {
            "ok": True,
            "drafts": [
                {
                    "plan_item_id": "P1",
                    "action": "update_existing",
                    "candidate_id": "TC1",
                    "use_case": "Updated case",
                    "expected_input": "Given: A=2",
                    "expected_output": "Then: B=1",
                }
            ],
        }

    def fake_retry(cfg, pack, plan, plan_item_ids, *, retry_notes=None):
        return {
            "ok": True,
            "drafts": [
                {
                    "plan_item_id": "P1",
                    "action": "update_existing",
                    "candidate_id": "TC1",
                    "use_case": "Updated case",
                    "expected_input": "Given: A=2",
                    "expected_output": "Then: B=1",
                }
            ],
        }

    monkeypatch.setattr("web.copilot_orchestrator.write_drafts_via_m365", fake_write)
    monkeypatch.setattr("web.copilot_orchestrator.write_retry_for_plan_items", fake_retry)
    cfg = {"assist": {"copilot_write_retries": 1}}
    out = run_write(bundle, "LB1", cfg)
    assert out["ok"] is True
    assert out["retry_count"] == 1
    assert out["noop_count"] == 0
