from __future__ import annotations

from src.engine.signal_constraint_parser import (
    extract_signal_constraints_from_text,
    is_locally_parseable,
    parse_signal_constraint_line,
)


def test_equality_with_label() -> None:
    parsed = parse_signal_constraint_line("HUY = 3 (RUN)")
    assert parsed == ("HUY", "= 3 (RUN)")


def test_range_with_signal() -> None:
    parsed = parse_signal_constraint_line("HUY >= 1, < 5")
    assert parsed == ("HUY", "range inclusive 1–5")


def test_range_short_form() -> None:
    parsed = parse_signal_constraint_line("VEH_SPD 7-16")
    assert parsed == ("VEH_SPD", "range inclusive 7–16")


def test_bare_range_uses_focus_term() -> None:
    parsed = parse_signal_constraint_line(">= 1, < 5", focus_term="HUY")
    assert parsed == ("HUY", "range inclusive 1–5")


def test_plain_value_uses_focus_term() -> None:
    parsed = parse_signal_constraint_line("100", focus_term="VEHICLE_STOPPED")
    assert parsed == ("VEHICLE_STOPPED", "= 100")


def test_extract_multiple_comma_separated() -> None:
    found = extract_signal_constraints_from_text("CND_A=1, CND_B=0")
    assert found["CND_A"] == "= 1"
    assert found["CND_B"] == "= 0"


def test_is_locally_parseable() -> None:
    assert is_locally_parseable("HUY >= 1, < 5")
    assert not is_locally_parseable("Vehicle speed means road speed in urban areas")
