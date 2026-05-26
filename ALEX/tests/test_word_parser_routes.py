from __future__ import annotations

from src.parsers.word_parser import _is_two_column_logic_table, _flat_fallback_logic_blocks


def test_is_two_column_logic_table_event_condition() -> None:
    header = ["event", "condition"]
    assert _is_two_column_logic_table(header) is True


def test_is_two_column_logic_table_judgment_condition() -> None:
    header = ["mid-garage mode judgment", "condition"]
    assert _is_two_column_logic_table(header) is True


def test_is_two_column_logic_table_signal_condition() -> None:
    header = ["kcc signal", "condition"]
    assert _is_two_column_logic_table(header) is True


def test_flat_fallback_logic_blocks_from_unmatched_table() -> None:
    grid = [
        ["Permission", "Condition"],
        ["ALLOFF allowed", "IGP status *2"],
        ["", "No vehicle speed *4"],
    ]
    blocks = _flat_fallback_logic_blocks(
        [grid],
        file_name="spec.docx",
        src_base={"file": "spec.docx"},
        skip_indices=set(),
    )
    assert len(blocks) == 2
    assert blocks[0]["parse_status"] == "partial"
