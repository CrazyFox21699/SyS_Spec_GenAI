from __future__ import annotations

from src.engine.testspec_validator import validate_workbook_io


def test_validate_good_io() -> None:
    result = validate_workbook_io(
        "Precondition: System state = RUN\nGiven: MODE_STS=1",
        "Then: PWR_STATE=1",
    )
    assert result["ok"] is True
    assert result["quality_score"] >= 80
    assert not any(i["severity"] == "error" for i in result["issues"])


def test_validate_rejects_generic_prose() -> None:
    result = validate_workbook_io(
        "Given: Satisfy all guards including timing as interpreted",
        "Then: PWR_STATE=1",
    )
    assert result["ok"] is False
    assert any(i["code"] == "generic_prose" for i in result["issues"])


def test_validate_rejects_dict_like() -> None:
    result = validate_workbook_io("{'current_state': None}", "Then: X=1")
    assert result["ok"] is False
    assert any(i["code"] == "dict_like" for i in result["issues"])
