"""Tests for Word section router and backward-compatible word extraction."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from src.models.spec_profile import LogicZone
from src.parsers.word_parser import extract_word_document
from src.parsers.word_section_router import build_word_section_map, zone_for_table

SHUTOFF = (
    Path(__file__).resolve().parents[2]
    / "pm_sample_inputs"
    / "input"
    / "edited_Shutoff_Condition_Spec.docx"
)


def _core_extract_payload(data: dict) -> dict:
    """Strip additive Phase-0 fields for baseline comparison."""
    out = dict(data)
    out.pop("spec_profile", None)
    out.pop("word_section_map", None)
    for block in out.get("logic_blocks") or []:
        src = block.get("source")
        if isinstance(src, dict):
            src.pop("section_zone", None)
    for row in out.get("condition_definitions") or []:
        src = row.get("source")
        if isinstance(src, dict):
            src.pop("section_zone", None)
    return out


def test_shutoff_section_map_detects_control_conditions():
    if not SHUTOFF.exists():
        return
    doc = Document(str(SHUTOFF))
    section_map = build_word_section_map(doc)
    sections = section_map.get("sections") or []
    zones = {s.get("zone") for s in sections}
    assert "overview" in zones
    assert "control_conditions" in zones
    assert zone_for_table(0, section_map) == LogicZone.control_conditions


def test_word_extract_flag_off_matches_baseline_shape():
    if not SHUTOFF.exists():
        return
    baseline = _core_extract_payload(extract_word_document(SHUTOFF))
    again = _core_extract_payload(extract_word_document(SHUTOFF, cfg={"features": {}}))
    assert len(baseline.get("logic_blocks") or []) == len(again.get("logic_blocks") or [])
    assert len(baseline.get("logic_blocks") or []) >= 1
    names_a = {b.get("name") for b in baseline.get("logic_blocks") or []}
    names_b = {b.get("name") for b in again.get("logic_blocks") or []}
    assert names_a == names_b


def test_word_extract_flag_on_adds_section_zone_metadata():
    if not SHUTOFF.exists():
        return
    cfg = {"features": {"word_section_router": True}}
    data = extract_word_document(SHUTOFF, cfg=cfg)
    profile = data.get("spec_profile") or {}
    assert profile.get("is_logic_spec") is True
    assert any(z.get("zone") == "control_conditions" for z in profile.get("section_zones") or [])
    blocks = data.get("logic_blocks") or []
    assert blocks
    assert any(
        (b.get("source") or {}).get("section_zone") == "control_conditions"
        for b in blocks
    )


def test_word_extract_flag_off_has_empty_section_map():
    if not SHUTOFF.exists():
        return
    data = extract_word_document(SHUTOFF, cfg={"features": {"word_section_router": False}})
    assert data.get("word_section_map") == {}
    assert data.get("spec_profile", {}).get("section_zones") == []
