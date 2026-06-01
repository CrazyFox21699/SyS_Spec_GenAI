"""Bundle import is text-only (no YAML validation at import time)."""

from __future__ import annotations

from pathlib import Path

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
REAL_COPILOT_BUNDLE = (_FIXTURES / "copilot_config_bundle_real.md").read_text(encoding="utf-8")

from web.config_bundle_copilot import normalize_copilot_markdown_bundle
from web.config_bundle_layers import (
    analyze_config_bundle,
    apply_bundle_import_sections,
    preview_config_bundle,
)

FULL_COPILOT_BUNDLE = r"""
\===== ALEX\_CODE\_CONFIG\_BUNDLE\_START =====

## 1. code\_rules.md
some rules

## 2. signal\_mapping.yaml

WMODE\_CMD:
setter: EXPECT\_CALL(rte, Rte\_Read\_XXX(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

DRDYSTS:
setter:
\- EXPECT\_CALL(...)
\- EXPECT\_CALL(...)

## 3. gtest\_template.md
```cpp
TEST_F({fixture}, {test_name}) {}
4. api_catalog.yaml

fixture:
RteDefaultAction

5. ai_review_pack.md

review prompt

===== ALEX_CODE_CONFIG_BUNDLE_END =====
"""


def test_normalize_unescapes_filenames_and_markers() -> None:
    n = normalize_copilot_markdown_bundle(FULL_COPILOT_BUNDLE)
    assert "code_rules.md" in n
    assert "WMODE_CMD" in n
    assert "EXPECT_CALL" in n
    assert "ALEX_CODE_CONFIG_BUNDLE_START" in n
    assert r"\_" not in n


def test_preview_all_five_sections_no_400(tmp_path: Path) -> None:
    preview = preview_config_bundle(tmp_path, FULL_COPILOT_BUNDLE)
    assert preview["ok"] is True
    detected = preview["detected_sections"]
    assert "code_rules.md" in detected
    assert "signal_mapping.yaml" in detected
    assert "gtest_template.md" in detected
    assert "api_catalog.yaml" in detected
    assert "ai_review_pack.md" in detected
    assert len(detected) == 5
    assert preview["import_diagnostics"]["yaml_validation"] == "not_performed"
    assert any("YAML validation is not performed" in w for w in preview["warnings"])
    assert "WMODE_CMD" in preview["sections"]["signal_mapping.yaml"]
    assert "EXPECT_CALL" in preview["sections"]["signal_mapping.yaml"]


def test_real_copilot_bundle_all_five_sections(tmp_path: Path) -> None:
    """Regression: full Copilot PM bundle (escaped markdown + invalid YAML)."""
    preview = preview_config_bundle(tmp_path, REAL_COPILOT_BUNDLE)
    assert preview["ok"] is True
    assert len(preview["detected_sections"]) == 5
    assert preview["missing_sections"] == []
    assert preview["copilot_normalized"] is True

    rules = preview["sections"]["code_rules.md"]
    assert "Fixture rule" in rules
    assert "EXPECT_CALL" in rules
    assert "ASSERT_*" in rules
    assert "igsw_Main_Run" in rules

    mapping = preview["sections"]["signal_mapping.yaml"]
    assert "WMODE_CMD:" in mapping
    assert "EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD" in mapping
    assert "DRDYSTS:" in mapping
    assert "direct_variable" in mapping
    assert "T_WAIT:" in mapping

    gtest = preview["sections"]["gtest_template.md"]
    assert "TEST_F({fixture}, {test_name})" in gtest
    assert "GIVEN" in gtest

    api = preview["sections"]["api_catalog.yaml"]
    assert "RteDefaultAction" in api
    assert "igsw_Main_Run()" in api

    review = preview["sections"]["ai_review_pack.md"]
    assert "[SUMMARY]" in review
    assert "[QUALITY_FINDINGS]" in review
    assert "QUALITY_FINDINGS" in review
    assert "ALEX_CODE_CONFIG_BUNDLE_END" not in review


def test_import_writes_sections_without_yaml_validation(tmp_path: Path) -> None:
    result = apply_bundle_import_sections(tmp_path, FULL_COPILOT_BUNDLE)
    assert result["ok"] is True
    assert len(result["applied_sections"]) == 5
    assert "WMODE_CMD" in result["sections"]["signal_mapping.yaml"]
    assert "EXPECT_CALL" in result["sections"]["signal_mapping.yaml"]
    assert "ALEX_CODE_CONFIG_BUNDLE_END" not in result["sections"]["ai_review_pack.md"]

    from web.config_bundle_layers import _overrides_dir

    mapping_text = (_overrides_dir(tmp_path) / "signal_mapping.yaml").read_text(encoding="utf-8")
    assert "WMODE_CMD" in mapping_text
