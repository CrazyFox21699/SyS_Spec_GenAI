"""Tests for Copilot-style config YAML parsers."""

from __future__ import annotations

from web.code_quality_gate import run_quality_gate
from web.config_yaml_parsers import (
    api_matches_catalog,
    build_mapping_match_index,
    flatten_signal_mapping,
    parse_api_catalog_full,
    parse_signal_mapping_yaml,
    resolve_signal_mapping_match,
)
COPILOT_SIGNAL_MAPPING = """
WMODE_CMD:
  setter: EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD(NotNull())).WillRepeatedly(Return(RTE_E_OK))

DRDYSTS:
  setter:
    - EXPECT_CALL(rte, Rte_Read_COMRX_COMP_DRDYSTS(NotNull()))
    - EXPECT_CALL(rte, Rte_Read_COMRX_DRDYSTS(NotNull()))

V_PMODE_STS:
  getter: direct_variable
  assertion: EXPECT_THAT(V_PMODE_STS, Eq({expected}))

T_WAIT:
  code: |
    for (int t = 0; t < {time}; ++t) {
        igsw_Main_Run();
    }
"""

LEGACY_SIGNAL_MAPPING = """
mappings:
  PMODE_STS:
    setter: SetSignal(PMODE_STS, value)
terms:
  ACCD:
    assertion: EXPECT_EQ(ACCD, expected)
"""

COPILOT_API_CATALOG = """
fixture:
  - RteDefaultAction
core:
  - igsw_Main_Run()
setters:
  - Rte_Read_*
getters:
  - V_PMODE_STS
assertions:
  - EXPECT_THAT(expr, Eq(value))
mocks:
  - EXPECT_CALL
  - WillRepeatedly
utilities:
  - NotNull()
  - Return()
"""

LEGACY_API_CATALOG = """
apis:
  - igsw_Main_Run
  - EXPECT_CALL
allowed:
  - SetArgPointee
"""


def test_top_level_signal_keys_detected() -> None:
    parsed = parse_signal_mapping_yaml(COPILOT_SIGNAL_MAPPING)
    assert parsed["format"]["top_level"] is True
    assert "WMODE_CMD" in parsed["keys"]
    assert "DRDYSTS" in parsed["keys"]
    assert "V_PMODE_STS" in parsed["keys"]
    assert "T_WAIT" in parsed["keys"]
    flat = flatten_signal_mapping(parsed)
    assert "WMODE_CMD" in flat
    assert "EXPECT_CALL" in flat["WMODE_CMD"]
    assert "igsw_Main_Run" in flat["T_WAIT"]


def test_legacy_mappings_terms_format() -> None:
    parsed = parse_signal_mapping_yaml(LEGACY_SIGNAL_MAPPING)
    assert parsed["format"]["reserved_schema"] is True
    assert "PMODE_STS" in parsed["keys"]
    flat = flatten_signal_mapping(parsed)
    assert "SetSignal" in flat["PMODE_STS"]


def test_list_setter_and_multiline_code() -> None:
    parsed = parse_signal_mapping_yaml(COPILOT_SIGNAL_MAPPING)
    drdy = parsed["signals"]["DRDYSTS"]
    assert isinstance(drdy["setter"], list)
    assert len(drdy["setter"]) >= 2
    assert "igsw_Main_Run" in flatten_signal_mapping(parsed)["T_WAIT"]


def _coerce_list_entries(val):
    from web.config_yaml_parsers import _coerce_snippet_list

    return _coerce_snippet_list(val)


def test_api_catalog_section_format() -> None:
    full = parse_api_catalog_full(COPILOT_API_CATALOG)
    assert full["format"]["section"] is True
    assert "igsw_Main_Run" in full["apis"]
    assert "EXPECT_THAT" in full["apis"]
    assert "Eq" in full["apis"]
    assert any("Rte_Read" in w for w in full["wildcards"])


def test_wildcard_api_match() -> None:
    full = parse_api_catalog_full(COPILOT_API_CATALOG)
    assert api_matches_catalog("Rte_Read_COMRX_DRDYSTS", full)
    assert not api_matches_catalog("TotallyUnknownApi", full)


def test_unknown_api_respects_wildcard() -> None:
    code = """
TEST_F(Fixture, TestName) {
  EXPECT_CALL(rte, Rte_Read_COMRX_SP1(NotNull()));
  igsw_Main_Run();
}
"""
    qg = run_quality_gate(code, candidate_id="TC1", api_catalog_yaml=COPILOT_API_CATALOG)
    unknown = [c for c in qg["checks"] if c["check_name"] == "unknown_api"]
    assert not unknown


def test_coverage_detects_top_level_key() -> None:
    gtest_state = {"code_variable_map": {}}
    config_files = {
        "signal_mapping.yaml": {"content": COPILOT_SIGNAL_MAPPING},
    }
    index = build_mapping_match_index(gtest_state, config_files)
    assert index["detected_mapping_count"] >= 4
    hit = resolve_signal_mapping_match("WMODE_CMD", index)
    assert hit is not None
    assert hit["source"] == "mapping_key"
    hit2 = resolve_signal_mapping_match("V_PMODE_STS", index)
    assert hit2 is not None


def test_coverage_case_insensitive_fallback() -> None:
    gtest_state = {"code_variable_map": {}}
    config_files = {"signal_mapping.yaml": {"content": "wmode_cmd:\n  setter: EXPECT_CALL(foo)\n"}}
    index = build_mapping_match_index(gtest_state, config_files)
    hit = resolve_signal_mapping_match("WMODE_CMD", index)
    assert hit is not None
    assert hit.get("case_insensitive") is True


def test_legacy_api_catalog_list() -> None:
    full = parse_api_catalog_full(LEGACY_API_CATALOG)
    assert "igsw_Main_Run" in full["apis"]
    assert "SetArgPointee" in full["apis"]


def test_fallback_parser_invalid_yaml_multiline() -> None:
    broken = """
WMODE_CMD:
setter: EXPECT_CALL(foo)

T_WAIT:
code: |
for (int t = 0; t < {time}; ++t) {
igsw_Main_Run();
}
"""
    parsed = parse_signal_mapping_yaml(broken)
    assert "WMODE_CMD" in parsed["keys"]
    assert parsed["yaml_status"] in ("WARNING", "OK")
    assert flatten_signal_mapping(parsed)["WMODE_CMD"]


def test_real_bundle_section_fallback() -> None:
    from pathlib import Path

    from web.config_bundle_layers import analyze_config_bundle

    text = Path("tests/fixtures/copilot_config_bundle_real.md").read_text(encoding="utf-8")
    sections = analyze_config_bundle(text)["sections"]
    parsed = parse_signal_mapping_yaml(sections["signal_mapping.yaml"])
    assert len(parsed["keys"]) >= 8
    assert "WMODE_CMD" in parsed["keys"]
