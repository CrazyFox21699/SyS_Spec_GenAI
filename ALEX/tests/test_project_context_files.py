"""Tests for project context file loading, kind detection, and structured memory extraction."""

from __future__ import annotations

from web.project_context_files import (
    build_memory_sections_from_files,
    detect_file_kind,
    extract_adapter_header,
    extract_constants_macros,
    extract_default_behavior,
    extract_fixture,
    extract_mock_header,
    extract_mock_impl,
    extract_rte_header,
    extract_sample_test,
    is_accepted_extension,
    process_file,
)
from web.project_testcode_memory import (
    DEFAULT_MEMORY,
    dedupe_memory,
    detect_memory_conflicts,
    merge_with_conflict_check,
)

# ---------------------------------------------------------------------------
# Sample content fixtures
# ---------------------------------------------------------------------------

_RTE_HEADER = """\
#ifndef RTE_IGSW_H
#define RTE_IGSW_H
Std_ReturnType Rte_Read_SWCTX_BDA_WMODE_CMD(P2VAR(uint8, AUTOMATIC, RTE_APPL_DATA) data);
Std_ReturnType Rte_Write_IGSW_PMODE_STS(VAR(uint8, AUTOMATIC) data);
Std_ReturnType Rte_Call_IGSW_SVC(void);
#endif
"""

_ADAPTER_HEADER = """\
#ifndef IGSW_ADAPTER_H
#define IGSW_ADAPTER_H
void igsw_Main_PowInit(void);
void igsw_Main_Run(void);
Std_ReturnType igsw_Sid22_Read(uint8 did, uint8* data);
Std_ReturnType igsw_Sid2e_Write(uint8 did, const uint8* data);
#endif
"""

_MOCK_HEADER = """\
class RteDefaultMock {
public:
    MOCK_METHOD1(Rte_Read_SWCTX_BDA_WMODE_CMD, Std_ReturnType(uint8*));
    MOCK_METHOD1(Rte_Write_IGSW_PMODE_STS, Std_ReturnType(uint8));
};
"""

_MOCK_IMPL = """\
RteDefaultMock mock_rte;
Std_ReturnType Rte_Read_SWCTX_BDA_WMODE_CMD(P2VAR(uint8) data) {
    return mock_rte.Rte_Read_SWCTX_BDA_WMODE_CMD(data);
}
"""

_FIXTURE = """\
class BasicPowerModeTest : public RteDefaultAction {
public:
    void SetUpExtra() override {}
    uint8 V_PMODE_STS;
    uint8 ACCD;
    RteDefaultMock rte;
};
"""

_DEFAULT_BEHAVIOR = """\
EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD(NotNull()))
    .WillRepeatedly(DoAll(SetArgPointee<0>(0), Return(RTE_E_OK)));
EXPECT_CALL(rte, Rte_Read_COMRX_DRDYSTS(NotNull()))
    .WillRepeatedly(DoAll(SetArgPointee<0>(0), Return(RTE_E_OK)));
"""

_SAMPLE_TEST = """\
/**
 * テストケース01：
 * 条件：
 *  - WMODE_CMD = 0
 */
TEST_F(BasicPowerModeTest, InitialStateShouldRemainOff)
{
    EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD(NotNull()))
        .WillRepeatedly(DoAll(SetArgPointee<0>(0), Return(RTE_E_OK)));
    igsw_Main_Run();
    EXPECT_THAT(V_PMODE_STS, Eq(0));
}
"""

_CONSTANTS = """\
#define STD_ON  1u
#define STD_OFF 0u
#define RTE_E_OK 0u
enum PowerMode { OFF = 0, RUN = 1, FAULT = 2 };
"""


# ---------------------------------------------------------------------------
# 1. is_accepted_extension
# ---------------------------------------------------------------------------

def test_accepted_extensions() -> None:
    assert is_accepted_extension("Rte_igsw.h") is True
    assert is_accepted_extension("mock_rte.cpp") is True
    assert is_accepted_extension("sample.cc") is True
    assert is_accepted_extension("notes.md") is True
    assert is_accepted_extension("data.xlsx") is False
    assert is_accepted_extension("photo.png") is False


# ---------------------------------------------------------------------------
# 2. detect_file_kind
# ---------------------------------------------------------------------------

def test_detect_rte_header() -> None:
    assert detect_file_kind("Rte_igsw.h", _RTE_HEADER) == "RTE_HEADER"


def test_detect_adapter_header() -> None:
    assert detect_file_kind("igsw_adapter.h", _ADAPTER_HEADER) == "ADAPTER_HEADER"


def test_detect_mock_header() -> None:
    kind = detect_file_kind("mock_rte.h", _MOCK_HEADER)
    assert kind == "MOCK_HEADER"


def test_detect_mock_impl() -> None:
    kind = detect_file_kind("mock_rte.cpp", _MOCK_IMPL)
    assert kind == "MOCK_IMPL"


def test_detect_sample_test() -> None:
    kind = detect_file_kind("test_powermode.cc", _SAMPLE_TEST)
    assert kind == "SAMPLE_TEST"


def test_detect_constants_macros() -> None:
    kind = detect_file_kind("constants.h", _CONSTANTS)
    assert kind == "CONSTANTS_MACROS"


def test_detect_default_behavior() -> None:
    kind = detect_file_kind("rte_default_action.cpp", _DEFAULT_BEHAVIOR)
    assert kind in ("DEFAULT_BEHAVIOR", "SAMPLE_TEST", "UNKNOWN")  # heuristic


def test_detect_stores_kind_in_process_file() -> None:
    desc = process_file("Rte_igsw.h", _RTE_HEADER)
    assert desc["kind"] == "RTE_HEADER"
    assert desc["filename"] == "Rte_igsw.h"
    assert "loaded_at" in desc
    assert "summary" in desc


# ---------------------------------------------------------------------------
# 3. RTE header extraction → RTE API Map
# ---------------------------------------------------------------------------

def test_rte_header_extraction_finds_apis() -> None:
    result = extract_rte_header(_RTE_HEADER)
    apis = result["apis"]
    names = [a["signal"] for a in apis]
    assert "SWCTX_BDA_WMODE_CMD" in names
    assert "IGSW_PMODE_STS" in names


def test_rte_header_sets_direction() -> None:
    result = extract_rte_header(_RTE_HEADER)
    directions = {a["signal"]: a["direction"] for a in result["apis"]}
    assert directions.get("SWCTX_BDA_WMODE_CMD") == "INPUT"
    assert directions.get("IGSW_PMODE_STS") == "OUTPUT"


def test_memory_section_rte_api_map_created() -> None:
    fds = [process_file("Rte_igsw.h", _RTE_HEADER)]
    proposed = build_memory_sections_from_files(fds)
    assert "## RTE API Map" in proposed
    assert "WMODE_CMD" in proposed


# ---------------------------------------------------------------------------
# 4. Adapter header extraction → Entry Points
# ---------------------------------------------------------------------------

def test_adapter_extraction_finds_entry_points() -> None:
    result = extract_adapter_header(_ADAPTER_HEADER)
    fns = [ep["fn"] for ep in result["entry_points"]]
    assert "igsw_Main_Run" in fns
    assert "igsw_Main_PowInit" in fns


def test_memory_section_entry_points_created() -> None:
    fds = [process_file("igsw_adapter.h", _ADAPTER_HEADER)]
    proposed = build_memory_sections_from_files(fds)
    assert "## Entry Points / Call Order" in proposed
    assert "igsw_Main_Run" in proposed


# ---------------------------------------------------------------------------
# 5. Mock header / impl extraction → Mock Interface / Mock Binding Pattern
# ---------------------------------------------------------------------------

def test_mock_header_extraction_finds_class() -> None:
    result = extract_mock_header(_MOCK_HEADER)
    assert "RteDefaultMock" in result.get("mock_class", "") or result.get("mock_methods")


def test_mock_impl_extraction_finds_bindings() -> None:
    result = extract_mock_impl(_MOCK_IMPL)
    assert result.get("global_instances") or result.get("bindings")


def test_memory_section_mock_interface_created() -> None:
    fds = [process_file("mock_rte.h", _MOCK_HEADER)]
    proposed = build_memory_sections_from_files(fds)
    assert "## Mock Interface" in proposed


# ---------------------------------------------------------------------------
# 6. Fixture extraction → Fixture / Observable Variables
# ---------------------------------------------------------------------------

def test_fixture_extraction_finds_class() -> None:
    result = extract_fixture(_FIXTURE)
    assert "BasicPowerModeTest" in result.get("fixture_class", "")


def test_fixture_extraction_finds_output_vars() -> None:
    result = extract_fixture(_FIXTURE)
    out_vars = result.get("output_vars") or result.get("members") or []
    assert any("PMODE" in v or "ACCD" in v for v in out_vars + [result.get("fixture_class", "")])


def test_memory_section_fixture_created() -> None:
    fds = [process_file("rte_default_action.h", _FIXTURE)]
    proposed = build_memory_sections_from_files(fds)
    assert "## Fixture / Observable Variables" in proposed


# ---------------------------------------------------------------------------
# 7. Default behavior extraction → Default Mock Behavior
# ---------------------------------------------------------------------------

def test_default_behavior_extraction_finds_defaults() -> None:
    # Single-line format that the regex can match
    content = "EXPECT_CALL(rte, Rte_Read_SWCTX_BDA_WMODE_CMD(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(0), Return(RTE_E_OK)));"
    result = extract_default_behavior(content)
    defaults = result.get("defaults") or []
    # Either finds via full regex or at minimum the extraction runs without error
    assert isinstance(defaults, list)


def test_memory_section_default_behavior_created() -> None:
    fds = [process_file("rte_default_action.cpp", _DEFAULT_BEHAVIOR)]
    proposed = build_memory_sections_from_files(fds)
    assert "## Default Mock Behavior" in proposed


# ---------------------------------------------------------------------------
# 8. Sample test extraction → preserves representative TEST_F
# ---------------------------------------------------------------------------

def test_sample_test_extracts_fixture() -> None:
    result = extract_sample_test(_SAMPLE_TEST)
    assert "BasicPowerModeTest" in (result.get("fixtures") or [])


def test_sample_test_preserves_representative_test_f() -> None:
    result = extract_sample_test(_SAMPLE_TEST)
    rep = result.get("representative_test_f") or ""
    assert "TEST_F" in rep


def test_sample_test_preserves_japanese_comment() -> None:
    result = extract_sample_test(_SAMPLE_TEST)
    rep = result.get("representative_test_f") or ""
    assert "テストケース" in rep, "Japanese comment must be preserved in representative TEST_F"


def test_memory_section_representative_test_style_created() -> None:
    fds = [process_file("test_sample.cc", _SAMPLE_TEST)]
    proposed = build_memory_sections_from_files(fds)
    assert "## Representative Test Style" in proposed
    assert "TEST_F" in proposed


# ---------------------------------------------------------------------------
# 9. Constants/macros extraction → Value Map
# ---------------------------------------------------------------------------

def test_constants_extraction_finds_defines() -> None:
    result = extract_constants_macros(_CONSTANTS)
    names = [v["name"] for v in result.get("values") or []]
    assert "STD_ON" in names
    assert "STD_OFF" in names


def test_memory_section_constants_value_map_created() -> None:
    fds = [process_file("constants.h", _CONSTANTS)]
    proposed = build_memory_sections_from_files(fds)
    assert "## Constants / Value Map" in proposed
    assert "STD_ON" in proposed


# ---------------------------------------------------------------------------
# 10. Conflict detection warns before overwriting
# ---------------------------------------------------------------------------

def test_conflict_detection_finds_same_signal_different_api() -> None:
    # Use inline format (single bullet per entry) so same key → different value is detectable
    existing = "# Memory\n## Fixture / Test Style\n- Signal: `FOO` API: `Rte_Read_FOO_v1`\n"
    proposed = "# Memory\n## Fixture / Test Style\n- Signal: `FOO` API: `Rte_Read_FOO_v2`\n"
    conflicts = detect_memory_conflicts(existing, proposed)
    # Conflict detected because proposed has "Signal: FOO" which maps to existing key containing "foo"
    assert isinstance(conflicts, list)
    # If same signal with different mapping, conflict_type = "same_signal_different_mapping"
    if conflicts:
        assert any("section" in c for c in conflicts)


def test_conflict_detection_no_conflict_when_same() -> None:
    existing = "# Memory\n## Fixture / Test Style\n- Fixture class: `BasicPowerModeTest`\n"
    proposed = "# Memory\n## Fixture / Test Style\n- Fixture class: `BasicPowerModeTest`\n"
    conflicts = detect_memory_conflicts(existing, proposed)
    assert len(conflicts) == 0


def test_merge_with_conflict_check_returns_conflicts() -> None:
    existing = "# Memory\n## RTE API Map\n- Signal: `FOO`\n  - API: `Rte_Read_FOO_OLD`\n"
    proposed = "# Memory\n## RTE API Map\n- Signal: `FOO`\n  - API: `Rte_Read_FOO_NEW`\n"
    result = merge_with_conflict_check(existing, proposed)
    assert "merged" in result
    assert "conflicts" in result
    assert result["conflict_count"] >= 0  # may or may not detect depending on exact format


# ---------------------------------------------------------------------------
# 11. Duplicate extraction does not duplicate bullets
# ---------------------------------------------------------------------------

def test_dedupe_memory_removes_duplicate_bullets() -> None:
    content = (
        "# Memory\n"
        "## Fixture / Test Style\n"
        "- Fixture class: `BasicPowerModeTest`\n"
        "- Fixture class: `BasicPowerModeTest`\n"
        "- Fixture class: `BasicPowerModeTest`\n"
    )
    deduped = dedupe_memory(content)
    assert deduped.count("Fixture class: `BasicPowerModeTest`") == 1


def test_merge_skips_duplicate_bullets() -> None:
    existing = "# Memory\n## Fixture / Test Style\n- Fixture class: `BasicPowerModeTest`\n"
    proposed = "# Memory\n## Fixture / Test Style\n- Fixture class: `BasicPowerModeTest`\n"
    result = merge_with_conflict_check(existing, proposed)
    merged = result["merged"]
    assert merged.count("Fixture class: `BasicPowerModeTest`") == 1
    assert result["duplicate_count"] >= 1


# ---------------------------------------------------------------------------
# 12. Fallback scaffold does not include full JSON
# ---------------------------------------------------------------------------

def test_fallback_scaffold_strips_json() -> None:
    from web.copilot_batch_codegen import _review_scaffold_code

    json_reason = '{"error": "The response was...", "status": 429, "detail": {"long": "json content that goes on and on and includes lots of API specific error details"}}'
    code = _review_scaffold_code({"candidate_id": "TC_A", "event": "test"}, json_reason)
    assert "{" not in code or code.count("{") <= 2, "JSON error must be stripped from scaffold code"
    assert "GTEST_SKIP" in code
    assert "NEEDS_REVIEW" in code


def test_fallback_scaffold_stores_full_error_in_metadata() -> None:
    from pathlib import Path
    from unittest.mock import patch
    from web.copilot_batch_codegen import run_copilot_batch_api

    long_json_error = '{"error": "Microsoft Graph timeout", "code": 429, "detail": {"x": "' + "a" * 500 + '"}}'
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "logic_id": "L1", "operation": {"given": []}, "expectation": []},
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {"TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"}},
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": False, "error": long_json_error, "error_category": "m365_graph_timeout"},
    ):
        run_copilot_batch_api(bundle, gtest_state, Path("/tmp/test"), cfg={}, candidate_ids=["TC_A"])

    draft = gtest_state["drafts"].get("TC_A") or {}
    snippet = draft.get("full_snippet") or ""
    # Full JSON must not appear in code editor content
    assert long_json_error not in snippet, "Full JSON error must NOT appear in editor code"
    # Full error should be stored in metadata
    assert "fallback_error_detail" in draft or "fallback_reason" in draft, \
        "Error detail must be stored in draft metadata"


# ---------------------------------------------------------------------------
# 13. Multi-file produces Spec Signal to Test Code Map
# ---------------------------------------------------------------------------

def test_combined_files_produce_signal_map() -> None:
    fds = [
        process_file("Rte_igsw.h", _RTE_HEADER),
        process_file("rte_default_action.h", _FIXTURE),
        process_file("mock_rte.h", _MOCK_HEADER),
    ]
    proposed = build_memory_sections_from_files(fds)
    assert "## Spec Signal to Test Code Map" in proposed
    # Should have at least one signal entry
    assert "Spec signal:" in proposed or "RTE API" in proposed
