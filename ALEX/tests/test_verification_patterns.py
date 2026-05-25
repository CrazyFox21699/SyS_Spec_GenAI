"""Tests for verification pattern mining."""

from __future__ import annotations

from src.engine.verification_patterns import (
    _given_fingerprint,
    _then_fingerprint,
    build_verification_matrix,
)
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview


def test_fingerprints_normalize_order() -> None:
    a = "Given: B=1\nGiven: A=2"
    b = "Given: A=2\nGiven: B=1"
    assert _given_fingerprint(a) == _given_fingerprint(b)


def test_one_to_many_detection() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "test_function": "f",
                "event": "e",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}], "when": []},
                "expectation": [{"signal": "OUT", "value": "0", "operator": "=="}],
            },
            {
                "id": "TC2",
                "test_function": "f",
                "event": "e2",
                "traceability": {"logic_block": "LB1"},
                "operation": {"given": [{"signal": "A", "value": "1", "operator": "=="}], "when": []},
                "expectation": [{"signal": "OUT", "value": "1", "operator": "=="}],
            },
        ],
        "ai_assists": {
            "candidate_overlays": {
                "TC1": {
                    "logic_id": "LB1",
                    "en": {"expected_input": "Given: A=1", "expected_output": "Then: OUT=0"},
                    "changed_fields": ["ExpectedInput", "ExpectedOutput"],
                },
                "TC2": {
                    "logic_id": "LB1",
                    "en": {"expected_input": "Given: A=1", "expected_output": "Then: OUT=1"},
                    "changed_fields": ["ExpectedInput", "ExpectedOutput"],
                },
            }
        },
    }
    matrix = build_verification_matrix(bundle, "LB1")
    assert matrix["one_to_many_count"] >= 1


def test_exporter_respects_engineer_empty_overlay() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC1",
                "test_function": "f",
                "event": "e",
                "operation": {"given": [{"signal": "X", "value": "9", "operator": "=="}], "when": []},
                "expectation": [{"signal": "Y", "value": "1", "operator": "=="}],
            }
        ],
        "ai_assists": {
            "candidate_overlays": {
                "TC1": {
                    "en": {"expected_input": "", "expected_output": "Then: Y=1"},
                    "changed_fields": ["ExpectedInput", "ExpectedOutput"],
                }
            }
        },
    }
    preview = build_customer_testspec_preview(bundle)
    row = preview["rows"][0]
    assert row["expected_input"] == ""
    assert "Given: X=9" not in row["expected_input"]
