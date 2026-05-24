from __future__ import annotations

from src.parsers.two_column_table_parser import _parse_constant_table


def test_timing_constant_with_tolerance_is_ok() -> None:
    body = [
        ["T_CANCEL", "Operator cancel filter time", "700 [ms] 20"],
        ["T_COMM_TIMEOUT", "Communication lost timeout", "123 [ms] 3"],
        ["T_REQ_STABLE", "Request stable confirmation time", "120 [ms] 5"],
    ]
    table = _parse_constant_table(body, {"file": "spec.docx"}, "T9")
    assert table.table_kind == "constant"
    assert all(row.issue_status == "ok" for row in table.rows)
    assert "tolerance=±20" in table.rows[0].parsed_hint
    assert "tolerance=±3" in table.rows[1].parsed_hint
    assert "tolerance=±5" in table.rows[2].parsed_hint


def test_timing_constant_without_tolerance() -> None:
    body = [["T_DELAY", "Delay", "50 [ms]"]]
    table = _parse_constant_table(body, {"file": "spec.docx"}, "T9")
    assert table.rows[0].issue_status == "ok"
    assert table.rows[0].parsed_hint == "value=50 unit=ms"
