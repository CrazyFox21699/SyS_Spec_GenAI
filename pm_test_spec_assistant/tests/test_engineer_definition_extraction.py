from __future__ import annotations

from web.main import _extract_engineer_definitions


def test_extract_engineer_definitions_supports_mean_pattern() -> None:
    rows = _extract_engineer_definitions("VEH_SPD mean Vehicle speed", "LOGIC_1")
    assert rows["VEH_SPD"]["definition"] == "Vehicle speed"


def test_extract_engineer_definitions_uses_focus_term_for_plain_text() -> None:
    rows = _extract_engineer_definitions("Vehicle speed", "LOGIC_1", "VEH_SPD")
    assert rows["VEH_SPD"]["definition"] == "Vehicle speed"


def test_comma_separated_signals() -> None:
    rows = _extract_engineer_definitions("CND_NORMAL_ROUTE=1, CND_BACKUP_ROUTE=0", "L1")
    assert rows["CND_NORMAL_ROUTE"]["definition"] == "1"
    assert rows["CND_BACKUP_ROUTE"]["definition"] == "0"


def test_all_missing_shorthand() -> None:
    missing = ["CND_BACKUP_ROUTE", "POWER=OFF"]
    rows = _extract_engineer_definitions(
        "all missing = 100", "TC2_T2_01", "CND_NORMAL_ROUTE", missing_terms=missing
    )
    assert rows["CND_BACKUP_ROUTE"]["definition"] == "= 100"
    assert "CND_NORMAL_ROUTE" not in rows


def test_range_with_focus_term() -> None:
    rows = _extract_engineer_definitions(">= 1, < 5", "TC2_T1_01", "HUY")
    assert rows["HUY"]["definition"] == "range inclusive 1–5"


def test_equality_with_state_label() -> None:
    rows = _extract_engineer_definitions("HUY = 3 (RUN)", "TC2_T1_01", "HUY")
    assert rows["HUY"]["definition"] in ("= 3 (RUN)", "3 (RUN)")
    note = "CND_NORMAL_ROUTE=1, all remaining missing definitions are equal to 100"
    missing = ["CND_BACKUP_ROUTE", "CND_BACKUP_TIMER_OK", "POWER=OFF", "CND_OUTPUT_READY"]
    rows = _extract_engineer_definitions(
        note, "TC2_T2_01", "CND_NORMAL_ROUTE", missing_terms=missing
    )
    assert rows["CND_NORMAL_ROUTE"]["definition"] == "1"
    assert rows["CND_BACKUP_ROUTE"]["definition"] == "= 100"
    assert rows["POWER=OFF"]["definition"] == "= 100"
    assert "CND_OUTPUT_READY" in rows
