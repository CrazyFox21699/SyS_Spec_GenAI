from __future__ import annotations

from src.parsers.excel_parser import _sheet_names_for_workbook


def test_sheet_names_respects_max_sheets(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.parsers.excel_parser._excel_ingest_config",
        lambda: {"max_sheets": 2, "sheet_include_patterns": []},
    )
    names = _sheet_names_for_workbook(["A", "B", "C", "D"])
    assert names == ["A", "B"]


def test_sheet_names_include_patterns(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.parsers.excel_parser._excel_ingest_config",
        lambda: {"max_sheets": 20, "sheet_include_patterns": [r"^TestSpec"]},
    )
    names = _sheet_names_for_workbook(["Notes", "TestSpec_EN", "Logic"])
    assert names == ["TestSpec_EN"]
