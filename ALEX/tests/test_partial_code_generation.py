"""Tests for partial code generation, TODO_REVIEW handling, and testcase sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from web.code_quality_gate import is_partial_generated_code, run_quality_gate, quality_to_code_status
from web.copilot_batch_codegen import build_copilot_batch_prompts, run_copilot_batch_api

# ---------------------------------------------------------------------------
# Sample code fixtures
# ---------------------------------------------------------------------------

_PARTIAL_CODE = """\
// TC_A
// Given: SIG_X=1
TEST_F(PowerModeTest, TC_A) {
  // Given setup — TODO_REVIEW: signal SIG_X mapping unknown
  in.sig_x = 1;  // TODO_REVIEW: verify correct member name
  igsw_Main_Run();
  // Then: out.mode == 1 — TODO_REVIEW: check assertion style
  EXPECT_EQ(out.mode, 1);
}
"""

_CLEAN_CODE = """\
// TC_B
TEST_F(PowerModeTest, TC_B) {
  EXPECT_CALL(rte, Rte_Read_SIG_X(NotNull()))
    .WillRepeatedly(DoAll(SetArgPointee<0>(1), Return(RTE_E_OK)));
  igsw_Main_Run();
  EXPECT_THAT(out.mode, Eq(1));
}
"""

_FALLBACK_SCAFFOLD = """\
// TC_C
// NEEDS_REVIEW: Copilot API fallback scaffold.
TEST(AlexGeneratedFallback, TC_C) {
  GTEST_SKIP() << "NEEDS_REVIEW: Microsoft endpoint timed out.";
}
"""

_BATCH_OUT_PARTIAL = """\
[TESTCASE_CODE]
testcase_id: TC_A
```cpp
// TC_A
TEST_F(PowerModeTest, TC_A) {
  in.sig_x = 1;  // TODO_REVIEW: verify correct member name
  igsw_Main_Run();
  EXPECT_EQ(out.mode, 1);  // TODO_REVIEW: verify assertion
}
```
[UNRESOLVED]
none
[ASSUMPTIONS]
- used best-effort from partial testcase data
"""


# ---------------------------------------------------------------------------
# 1. is_partial_generated_code detection
# ---------------------------------------------------------------------------

def test_is_partial_real_code_with_todo_review() -> None:
    assert is_partial_generated_code(_PARTIAL_CODE) is True


def test_is_partial_false_for_clean_code() -> None:
    assert is_partial_generated_code(_CLEAN_CODE) is False


def test_is_partial_false_for_fallback_scaffold() -> None:
    """Fallback scaffold is NOT partial generated code."""
    assert is_partial_generated_code(_FALLBACK_SCAFFOLD) is False


def test_is_partial_false_for_empty() -> None:
    assert is_partial_generated_code("") is False


# ---------------------------------------------------------------------------
# 2. Quality gate: TODO_REVIEW → WARNING (NEEDS_REVIEW), not ERROR
# ---------------------------------------------------------------------------

def test_todo_review_code_is_warning_not_fail() -> None:
    qg = run_quality_gate(_PARTIAL_CODE, candidate_id="TC_A")
    assert qg["summary"] == "WARNING", "partial code with TODO_REVIEW must be WARNING"
    assert quality_to_code_status(qg["summary"]) == "NEEDS_REVIEW"
    assert any(c["check_name"] == "todo_review" for c in qg["checks"])


def test_todo_review_code_not_error() -> None:
    qg = run_quality_gate(_PARTIAL_CODE, candidate_id="TC_A")
    assert quality_to_code_status(qg["summary"]) != "ERROR"


# ---------------------------------------------------------------------------
# 3. Partial code preserved and visible in draft
# ---------------------------------------------------------------------------

def test_partial_code_persisted_as_needs_review(tmp_path: Path) -> None:
    """Partial code with TODO_REVIEW must be stored as NEEDS_REVIEW, not ERROR."""
    from web.gtest_workspace import persist_generated_draft_workflow

    bundle: dict = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "logic_blocks": [],
        "signals": [],
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    persist_generated_draft_workflow(
        bundle,
        gtest_state,
        candidate_id="TC_A",
        draft_payload={"full_snippet": _PARTIAL_CODE},
        generation_source="COPILOT_BATCH",
    )

    draft = gtest_state["drafts"].get("TC_A") or {}
    assert draft.get("code_status") == "NEEDS_REVIEW", "partial code must be NEEDS_REVIEW"
    snippet = draft.get("full_snippet") or draft.get("code_body") or ""
    assert "TODO_REVIEW" in snippet, "partial code must remain visible/editable"
    assert draft.get("is_partial_code") is True
    assert draft.get("issue_reason") == "partial_code_todo_review"


def test_partial_code_not_discarded(tmp_path: Path) -> None:
    """Partial code with TODO_REVIEW must not be discarded — full_snippet must be non-empty."""
    from web.gtest_workspace import persist_generated_draft_workflow

    bundle: dict = {"test_candidates": [], "logic_blocks": [], "signals": []}
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    persist_generated_draft_workflow(
        bundle,
        gtest_state,
        candidate_id="TC_X",
        draft_payload={"full_snippet": _PARTIAL_CODE},
    )

    draft = gtest_state["drafts"].get("TC_X") or {}
    assert (draft.get("full_snippet") or draft.get("code_body") or "").strip(), \
        "partial code must not be discarded"


# ---------------------------------------------------------------------------
# 4. Fallback scaffold vs partial generated code are distinguishable
# ---------------------------------------------------------------------------

def test_fallback_scaffold_marked_correctly(tmp_path: Path) -> None:
    """Fallback scaffold (GTEST_SKIP) has is_fallback_scaffold=True, is_partial_code=False."""
    from web.gtest_workspace import persist_generated_draft_workflow

    bundle: dict = {"test_candidates": [], "logic_blocks": [], "signals": []}
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    persist_generated_draft_workflow(
        bundle,
        gtest_state,
        candidate_id="TC_C",
        draft_payload={
            "full_snippet": _FALLBACK_SCAFFOLD,
            "is_fallback_scaffold": True,
            "issue_reason": "fallback_scaffold_timeout",
        },
    )

    draft = gtest_state["drafts"].get("TC_C") or {}
    assert draft.get("is_fallback_scaffold") is True
    assert draft.get("is_partial_code") is False
    assert draft.get("issue_reason") == "fallback_scaffold_timeout"


def test_partial_code_not_confused_with_fallback(tmp_path: Path) -> None:
    """Real partial code must NOT be marked as is_fallback_scaffold."""
    from web.gtest_workspace import persist_generated_draft_workflow

    bundle: dict = {"test_candidates": [], "logic_blocks": [], "signals": []}
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    persist_generated_draft_workflow(
        bundle,
        gtest_state,
        candidate_id="TC_A",
        draft_payload={"full_snippet": _PARTIAL_CODE},
    )

    draft = gtest_state["drafts"].get("TC_A") or {}
    assert draft.get("is_fallback_scaffold") is False or not draft.get("is_fallback_scaffold")
    assert draft.get("is_partial_code") is True


# ---------------------------------------------------------------------------
# 5. Prompt requests partial/best-effort code
# ---------------------------------------------------------------------------

def test_prompt_requests_best_effort_partial_code() -> None:
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {"TC_A": {"expected_input": "Given: X=1", "expected_output": ""}},
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True
    prompt = result["prompts"][0]["prompt"]
    assert "TODO_REVIEW" in prompt, "prompt must instruct Copilot to use TODO_REVIEW"
    # "best-effort" or "concrete" or "as much code as possible"
    assert any(kw in prompt.lower() for kw in ("best-effort", "partial", "concrete", "as much"))


def test_testcase_with_missing_output_still_included_in_chunk() -> None:
    """TC with empty expected_output must NOT be silently dropped from API chunk."""
    bundle = {
        "test_candidates": [
            {"id": "TC_EMPTY_OUT", "operation": {"given": [{"signal": "X", "value": "1"}]}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {"TC_EMPTY_OUT": {"expected_input": "Given: X=1", "expected_output": ""}},
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_EMPTY_OUT"], allow_missing_sample=True
    )
    assert result["ok"] is True
    all_ids = [cid for p in result["prompts"] for cid in p["candidate_ids"]]
    assert "TC_EMPTY_OUT" in all_ids, "TC with missing output must be included in chunk"


# ---------------------------------------------------------------------------
# 6. Copilot returns partial code → NEEDS_REVIEW, not ERROR
# ---------------------------------------------------------------------------

def test_copilot_partial_code_response_saved_as_needs_review(tmp_path: Path) -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [],
            }
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": ""},
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": True, "reply": _BATCH_OUT_PARTIAL},
    ):
        out = run_copilot_batch_api(
            bundle, gtest_state, tmp_path, cfg={}, candidate_ids=["TC_A"], batch_size=1
        )

    draft = gtest_state["drafts"].get("TC_A") or {}
    assert draft.get("code_status") in ("NEEDS_REVIEW", "SAVED"), \
        "partial code must not be ERROR"
    assert (draft.get("full_snippet") or draft.get("code_body") or "").strip(), \
        "partial code must remain visible"


# ---------------------------------------------------------------------------
# 7. Excel/import order preserved in all batch scopes
# ---------------------------------------------------------------------------

def test_generate_all_preserves_excel_order() -> None:
    bundle = {
        "test_candidates": [
            {"id": "TC_Z", "operation": {"given": []}, "expectation": []},
            {"id": "TC_M", "operation": {"given": []}, "expectation": []},
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {
                "TC_Z": {"expected_input": "in", "expected_output": "out"},
                "TC_M": {"expected_input": "in", "expected_output": "out"},
                "TC_A": {"expected_input": "in", "expected_output": "out"},
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    result = build_copilot_batch_prompts(
        bundle, gtest_state, scope="all", allow_missing_sample=True
    )
    assert result["ok"] is True
    all_ids = [cid for p in result["prompts"] for cid in p["candidate_ids"]]
    assert all_ids == ["TC_Z", "TC_M", "TC_A"], \
        f"generate-all must preserve Excel import order; got {all_ids}"


# ---------------------------------------------------------------------------
# 8. issue_reason in drafts
# ---------------------------------------------------------------------------

def test_issue_reason_set_for_error_draft(tmp_path: Path) -> None:
    from web.gtest_workspace import persist_generated_draft_workflow

    bundle: dict = {"test_candidates": [], "logic_blocks": [], "signals": []}
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    # Empty code → ERROR (quality gate fails missing_TEST)
    persist_generated_draft_workflow(
        bundle, gtest_state,
        candidate_id="TC_E",
        draft_payload={"full_snippet": ""},
    )

    draft = gtest_state["drafts"].get("TC_E") or {}
    assert draft.get("code_status") == "ERROR"
    # issue_reason must be set for ERROR drafts (api_error or parse_error)
    assert draft.get("issue_reason") in ("api_error", "parse_error")
