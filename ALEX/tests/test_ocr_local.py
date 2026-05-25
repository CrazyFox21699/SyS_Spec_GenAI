from __future__ import annotations

from src.parsers.ocr_local import analyze_ocr_text


def test_analyze_ocr_text_extracts_definitions_and_transitions() -> None:
    text = """
    OK_SHUTOFF: CND_REQ_GROUP and CND_SAFE_GROUP are both true
    FORCE_SHUTOFF = TRUE or FORCE_REQ = TRUE
    NORMAL -> SHUT_OFF
    """

    parsed = analyze_ocr_text(text, source_file="diagram.png", source_kind="diagram_image_ocr")

    names = {row["name"] for row in parsed["condition_definitions"]}
    assert "OK_SHUTOFF" in names
    assert any(row.get("event") == "diagram_transition" for row in parsed["transitions"])
    assert any(row.get("name") == "FORCE_SHUTOFF" for row in parsed["state_rules"])
    assert parsed["ocr_text"]
