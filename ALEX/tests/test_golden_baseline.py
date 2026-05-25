from __future__ import annotations

from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

GOLDEN_BUNDLE = {
    "test_candidates": [
        {
            "id": "TC_PM_001",
            "test_function": "Power mode",
            "event": "transition",
            "use_case_description": "Positive path",
            "precondition": [{"current_state": "OFF"}],
            "operation": {
                "given": [{"signal": "MODE_STS", "value": 1}],
                "when": [],
            },
            "expectation": [{"signal": "PWR_STATE", "value": 1}],
            "traceability": {},
            "review_status": "pending",
        }
    ],
    "features_validator": True,
}


def test_golden_preview_concrete_io_and_validation() -> None:
    preview = build_customer_testspec_preview(GOLDEN_BUNDLE, validate_io=True)
    assert len(preview["rows"]) == 1
    row = preview["rows"][0]
    assert "Precondition: System state = OFF" in row["expected_input"]
    assert "Given: MODE_STS=1" in row["expected_input"]
    assert "Then: PWR_STATE=1" in row["expected_output"]
    assert "{'current_state'" not in row["expected_input"]
    val = row.get("validation") or {}
    assert val.get("ok") is True
    assert int(val.get("quality_score", 0)) >= 80
