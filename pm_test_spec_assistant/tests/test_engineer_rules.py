"""Given dedupe and Ollama patch application (no regex rule parser)."""

from src.engine.engineer_rules import (
    apply_given_patches_to_bundle,
    dedupe_given_by_signal,
    dedupe_logic_block_given,
)


def test_dedupe_given_by_signal_last_wins() -> None:
    given = [
        {"signal": "OK_SHUTOFF", "value": "1", "operator": "=="},
        {"signal": "FORCE_SHUTOFF", "value": "0", "operator": "=="},
        {"signal": "OK_SHUTOFF", "value": "10", "operator": "=="},
    ]
    out = dedupe_given_by_signal(given)
    by_sig = {g["signal"]: g["value"] for g in out}
    assert by_sig["OK_SHUTOFF"] == "10"
    assert len([g for g in out if g.get("signal")]) == 2


def test_apply_given_patches_to_bundle() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1"},
                "operation": {
                    "given": [
                        {"signal": "OK_SHUTOFF", "value": "1", "operator": "=="},
                        {"signal": "CND_FORCE_ALLOWED", "value": "0", "operator": "=="},
                    ]
                },
            },
        ],
    }
    patches = [
        {
            "candidate_id": "TC1",
            "given": [
                {"signal": "OK_SHUTOFF", "value": "10"},
                {"signal": "FORCE_SHUTOFF", "value": "6"},
                {"signal": "CND_FORCE_ALLOWED", "value": "1"},
            ],
        }
    ]
    n = apply_given_patches_to_bundle(bundle, "LB1", patches)
    assert n == 1
    given = bundle["test_candidates"][0]["operation"]["given"]
    by_sig = {g["signal"]: g["value"] for g in given}
    assert by_sig == {"OK_SHUTOFF": "10", "FORCE_SHUTOFF": "6", "CND_FORCE_ALLOWED": "1"}


def test_dedupe_logic_block_without_patches() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "traceability": {"logic_block": "LB1"},
                "operation": {
                    "given": [
                        {"signal": "OK_SHUTOFF", "value": "1", "operator": "=="},
                        {"signal": "OK_SHUTOFF", "value": "10", "operator": "=="},
                    ]
                },
            },
        ],
    }
    n = dedupe_logic_block_given(bundle, "LB1")
    assert n == 1
    assert len(bundle["test_candidates"][0]["operation"]["given"]) == 1
