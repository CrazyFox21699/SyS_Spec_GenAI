"""Smart Test Code workflow: context analyze, mapping proposals."""

from __future__ import annotations

from pathlib import Path

from web.test_code_smart_workflow import (
    _collect_cpp_corpus,
    _infer_rte_read_by_signal,
    _propose_one_mapping,
    accept_proposed_mappings,
    analyze_project_context,
    propose_missing_mappings,
)

SAMPLE_CPP = """
TEST_F(RteDefaultAction, SampleTest) {
  EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD(NotNull())).WillRepeatedly(Return(RTE_E_OK));
  igsw_Main_Run();
  EXPECT_THAT(V_PMODE_STS, Eq(1));
}
"""


def test_infer_rte_read_from_sample() -> None:
    m = _infer_rte_read_by_signal(SAMPLE_CPP)
    assert any("Rte_Read_SWCTX_BDA_WMODE_CMD" in fn for fn in m.get("WMODE", []) + m.get("CMD", []))


def test_propose_mapping_high_confidence() -> None:
    rte = _infer_rte_read_by_signal(SAMPLE_CPP)
    p = _propose_one_mapping("WMODE_CMD", rte, {"V_PMODE_STS"}, SAMPLE_CPP)
    assert p["confidence"] >= 0.85
    assert "EXPECT_CALL" in p["proposed_code"]


def test_analyze_project_context_writes_config(tmp_path: Path) -> None:
    bundle = {"test_candidates": [], "code_references": []}
    gtest_state = {"drafts": {}, "code_variable_map": {}}
    result = analyze_project_context(
        tmp_path,
        bundle,
        gtest_state,
        extra_snippets=[SAMPLE_CPP],
        force=True,
    )
    assert result["ok"] is True
    assert result.get("mapping_keys_inferred", 0) >= 1
    sm_path = tmp_path / "bundle" / "code_config" / "layers" / "project_overrides" / "signal_mapping.yaml"
    assert sm_path.exists()
    assert "WMODE" in sm_path.read_text(encoding="utf-8") or "EXPECT_CALL" in sm_path.read_text(encoding="utf-8")


def test_accept_proposed_mapping(tmp_path: Path) -> None:
    from web.config_bundle_layers import ensure_config_layers

    ensure_config_layers(tmp_path)
    gtest_state = {"drafts": {}, "code_variable_map": {}}
    items = [
        {
            "signal": "TEST_SIG",
            "proposed_code": "EXPECT_CALL(rte, Rte_Read_TEST_SIG(NotNull()))",
            "confidence": 0.95,
            "accept": True,
        }
    ]
    result = accept_proposed_mappings(tmp_path, gtest_state, items)
    assert result["ok"] is True
    assert len(result["accepted"]) == 1
    assert gtest_state["code_variable_map"]["TEST_SIG"]
