from __future__ import annotations

from src.engine.concrete_test_values import (
    definition_to_given_line,
    infer_boundary_value,
    materialize_expected_input,
    materialize_expected_output,
)
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview


def test_definition_to_given_line_skips_prose_and_truncation() -> None:
    prose = (
        "Safety interlock is active. The condition line is written as NOT SAFETY_LOCKED. "
        "The tool must provide concrete values."
    )
    assert definition_to_given_line("SAFETY_LOCKED", prose) is None
    assert definition_to_given_line("SAFETY_LOCKED", "= 100") == "Given: SAFETY_LOCKED=100"
    assert definition_to_given_line("OK_SHUTOFF", "1") == "Given: OK_SHUTOFF=1"


def test_infer_boundary_value_past_threshold() -> None:
    assert infer_boundary_value(">", "2 km/h") == "2.01 km/h"
    assert infer_boundary_value(">=", "5 ms") == "5.01 ms"


def test_materialize_skips_generic_when_and_uses_signals() -> None:
    candidate = {
        "precondition": [{"current_state": "OFF"}],
        "operation": {
            "given": [{"signal": "VEH_SPD", "value": 0, "operator": "=="}],
            "when": [{"description": "Satisfy all guards including timing as interpreted"}],
        },
        "expectation": [{"signal": "PWR_STATE", "value": 1}],
    }
    text = materialize_expected_input(candidate)
    assert "Precondition: System state = OFF" in text
    assert "Given: VEH_SPD=0" in text
    assert "Satisfy all guards" not in text
    out = materialize_expected_output(candidate)
    assert "Then: PWR_STATE=1" in out


def test_preview_uses_concrete_values_not_dict_precondition() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_PM_001",
                "test_function": "Power mode",
                "event": "transition",
                "use_case_description": "test",
                "precondition": [{"current_state": "RUN"}],
                "operation": {
                    "given": [{"signal": "MODE_STS", "value": 1}],
                    "when": [{"description": "Satisfy all guards including timing as interpreted"}],
                },
                "expectation": [{"description": "VMODE_STS becomes 1"}],
                "traceability": {},
            }
        ],
    }
    row = build_customer_testspec_preview(bundle)["rows"][0]
    assert "Precondition: System state = RUN" in row["expected_input"]
    assert "Given: MODE_STS=1" in row["expected_input"]
    assert "Then: VMODE_STS=1" in row["expected_output"]
    assert "{'current_state'" not in row["expected_input"]
