"""Tests for LogicZone mapping and spec profile helpers."""

from __future__ import annotations

from src.models.spec_profile import LogicZone, build_spec_profile, zone_from_section_title


def test_zone_from_numbered_control_conditions():
    assert zone_from_section_title("2. Control Conditions") == LogicZone.control_conditions


def test_zone_from_overview():
    assert zone_from_section_title("1. Overview") == LogicZone.overview


def test_zone_from_standalone_constants():
    assert zone_from_section_title("Constants") == LogicZone.constants


def test_zone_unknown_title():
    assert zone_from_section_title("Alias / Mixed Naming") == LogicZone.unknown


def test_build_spec_profile_shape():
    profile = build_spec_profile(
        file_name="sample.docx",
        is_logic_spec=True,
        classifier_score=0.72,
        classifier_signals=["logic_ops_in_tables"],
        section_zones=[{"title": "2. Control Conditions", "zone": "control_conditions"}],
    )
    assert profile["file"] == "sample.docx"
    assert profile["is_logic_spec"] is True
    assert profile["classifier_score"] == 0.72
    assert profile["section_zones"][0]["zone"] == "control_conditions"
