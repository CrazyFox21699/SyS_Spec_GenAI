"""Tests for Google Test skeleton codegen."""

from __future__ import annotations

from src.engine.gtest_codegen import (
    GTestHarnessConfig,
    build_gtest_skeleton,
    sanitize_test_name,
    suggest_variable_map,
)


def _sample_candidate() -> dict:
    return {
        "id": "TC_PM_001",
        "test_function": "Power mode",
        "event": "Shutdown_AllMandatory",
        "use_case_description": "Shutdown when all mandatory conditions met",
        "precondition": [{"current_state": "ADM1_ACC"}],
        "operation": {
            "given": [
                {"signal": "IGN_SW", "value": "0", "operator": "=="},
                {"signal": "Mode_cmd", "value": "1", "operator": "=="},
            ],
            "when": [{"timing": "elapsed_time >= 100 ms"}],
        },
        "expectation": [
            {"signal": "Mode_STS", "value": "0", "operator": "=="},
            {"description": "System state = ADM1_OFF"},
        ],
        "traceability": {"logic_block": "LOGIC_010", "control_name": "Shutdown decision"},
    }


def test_sanitize_test_name_from_candidate_id() -> None:
    assert sanitize_test_name("TC_PM_001", "Shutdown AllMandatory") == "TC_PM_001_Shutdown_AllMandatory"


def test_build_gtest_skeleton_aaa_blocks() -> None:
    harness = GTestHarnessConfig()
    variable_map = {"IGN_SW": "in.IGN_SW", "Mode_cmd": "in.Mode_cmd", "Mode_STS": "out.Mode_STS"}
    draft = build_gtest_skeleton(
        candidate=_sample_candidate(),
        variable_map=variable_map,
        harness=harness,
    )
    assert "TEST_F(PowerModeTest, TC_PM_001_Shutdown_AllMandatory)" in draft.code_body
    assert "in.IGN_SW = 0U;" in draft.code_body
    assert "RunForMs(100U);" in draft.code_body
    assert "EXPECT_EQ(out.Mode_STS, 0U);" in draft.code_body
    assert "EXPECT_EQ(state, PowerModeState::ADM1_OFF);" in draft.code_body
    assert "// Given: IGN_SW=0" in draft.spec_comment_block
    assert "// Logic:" not in draft.spec_comment_block or draft.spec_comment_block


def test_variable_map_reflected_in_body() -> None:
    harness = GTestHarnessConfig(inputs_member="inputs", outputs_member="outputs")
    variable_map = {"IGN_SW": "inputs.ign_sw"}
    draft = build_gtest_skeleton(
        candidate=_sample_candidate(),
        variable_map=variable_map,
        harness=harness,
    )
    assert "inputs.ign_sw = 0U;" in draft.code_body


def test_logic_only_mode_includes_expression_comment() -> None:
    logic_block = {
        "logic_id": "LOGIC_010",
        "control_name": "Shutdown decision",
        "raw_expression": "(HUY = OK OR OK_SHUTOFF = 1)",
    }
    draft = build_gtest_skeleton(logic_block=logic_block, variable_map={"HUY": "in.HUY"})
    assert "// Logic: (HUY = OK OR OK_SHUTOFF = 1)" in draft.spec_comment_block
    assert "TODO: set inputs" in draft.code_body or "EvaluatePowerMode" in draft.code_body
    assert draft.source_kind == "logic"


def test_unmapped_signal_uses_default_mapping() -> None:
    draft = build_gtest_skeleton(candidate=_sample_candidate(), variable_map={})
    assert "TODO(unmapped):" not in draft.code_body
    assert "in.IGN_SW = 0U;" in draft.code_body
    assert "EXPECT_EQ(out.Mode_STS, 0U);" in draft.code_body
    assert draft.unmapped_signals == []


def test_suggest_variable_map_scoped_to_triplet() -> None:
    harness = GTestHarnessConfig()
    given = "Given: PWR_REQ_VALID=1\nGiven: TR_OFF_ACC=0"
    then = "Then: IGN_STS=1"
    m = suggest_variable_map(
        harness=harness,
        given_when_text=given,
        then_text=then,
    )
    assert m["PWR_REQ_VALID"] == "in.PWR_REQ_VALID"
    assert m["TR_OFF_ACC"] == "in.TR_OFF_ACC"
    assert m["IGN_STS"] == "out.IGN_STS"
    assert "AND" not in m


def test_suggest_variable_map_from_signals() -> None:
    harness = GTestHarnessConfig()
    m = suggest_variable_map(
        signals=[{"name": "IGN_SW"}],
        harness=harness,
    )
    assert m["IGN_SW"] == "in.IGN_SW"
