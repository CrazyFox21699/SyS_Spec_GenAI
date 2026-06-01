"""Tests for Copilot-escaped alex_code_config_bundle.md normalization."""

from __future__ import annotations

from pathlib import Path

from web.config_bundle_copilot import (
    normalize_copilot_markdown_bundle,
    repair_yaml_config_section,
)
from web.config_bundle_layers import analyze_config_bundle, preview_config_bundle, propose_config_bundle


COPILOT_ESCAPED_SAMPLE = r"""
\===== ALEX\_CODE\_CONFIG\_BUNDLE\_START =====

## 1. signal\_mapping.yaml

WMODE\_CMD:
setter: EXPECT\_CALL(rte, Rte\_Read\_XXX(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

DRDYSTS:
setter:
\- EXPECT\_CALL(a, b)
\- EXPECT\_CALL(c, d)

## 4. api\_catalog.yaml

fixture:
\* RteDefaultAction

\===== ALEX\_CODE\_CONFIG\_BUNDLE\_END =====
"""


def test_normalize_unescapes_markers_and_headings() -> None:
    n = normalize_copilot_markdown_bundle(COPILOT_ESCAPED_SAMPLE)
    assert "ALEX_CODE_CONFIG_BUNDLE_START" in n
    assert "signal_mapping.yaml" in n
    assert "WMODE_CMD" in n
    assert r"\_" not in n or "code\\_rules" not in n


def test_analyze_detects_sections_from_copilot_sample() -> None:
    a = analyze_config_bundle(COPILOT_ESCAPED_SAMPLE)
    assert "signal_mapping.yaml" in a["detected_sections"]
    assert "api_catalog.yaml" in a["detected_sections"]
    assert a["copilot_normalized"] is True
    assert any("normalized" in w.lower() for w in a["warnings"])


def test_preview_not_plain_400_for_copilot_sample(tmp_path: Path) -> None:
    preview = preview_config_bundle(tmp_path, COPILOT_ESCAPED_SAMPLE)
    assert preview["ok"] is True
    assert preview.get("detected_sections")
    assert "normalized_preview" in preview
    assert preview.get("import_diagnostics", {}).get("yaml_validation") == "not_performed"


def test_propose_fills_section_texts(tmp_path: Path) -> None:
    result = propose_config_bundle(tmp_path, COPILOT_ESCAPED_SAMPLE)
    assert result["ok"] is True
    assert "signal_mapping.yaml" in (result.get("detected_sections") or [])


def test_numbered_escaped_heading() -> None:
    md = "## 1. code\\_rules.md\n\n# Rule\n"
    a = analyze_config_bundle(md)
    assert "code_rules.md" in a["detected_sections"]


def test_triple_hash_escaped() -> None:
    md = "### signal\\_mapping.yaml\n\nterms:\n  X: y\n"
    a = analyze_config_bundle(md)
    assert "signal_mapping.yaml" in a["detected_sections"]


def test_repair_quotes_cpp_setter() -> None:
    raw = r"WMODE_CMD:\nsetter: EXPECT\_CALL(foo, bar)\n"
    repaired, warns, err = repair_yaml_config_section(raw, "signal_mapping.yaml")
    assert "WMODE_CMD" in repaired
    assert "EXPECT_CALL" in repaired
    assert '"' in repaired or err is None


def test_invalid_no_sections_clear_error(tmp_path: Path) -> None:
    preview = preview_config_bundle(tmp_path, "hello world only")
    assert preview["ok"] is False
    assert preview.get("error")
