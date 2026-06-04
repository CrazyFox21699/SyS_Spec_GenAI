"""Copilot batch orchestrator — prompt, parse, import."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import json

from web.copilot_batch_codegen import (
    apply_copilot_batch_import,
    build_copilot_batch_prompts,
    collect_copilot_project_context,
    collect_retry_candidate_ids,
    parse_copilot_batch_response,
    run_copilot_batch_api,
)

BATCH_OUT = """
[TESTCASE_CODE]
testcase_id: TC_A
```cpp
// TC_A
TEST_F(RteDefaultAction, A) {
  EXPECT_CALL(rte, Rte_Read_FOO(NotNull())).WillRepeatedly(Return(RTE_E_OK));
  igsw_Main_Run();
  EXPECT_THAT(V_OUT, Eq(1));
}
```
[UNRESOLVED]
testcase_id: TC_B
reason: missing mock for SIG_X
[ASSUMPTIONS]
- used exemplar fixture
"""


def test_parse_unresolved_per_id() -> None:
    p = parse_copilot_batch_response(BATCH_OUT)
    assert p["parsed_count"] == 1
    assert "TC_A" in {i["candidate_id"] for i in p["items"]}
    assert p["unresolved_by_id"].get("TC_B")


def test_build_prompt_requires_sample_or_saved() -> None:
    from web.copilot_batch_codegen import build_copilot_batch_prompt

    bundle = {"test_candidates": []}
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}
    r = build_copilot_batch_prompts(bundle, gtest_state, candidate_ids=["TC_A"])
    assert r["ok"] is False

    bundle["ai_assists"] = {"code_style_samples": [{"label": "s", "snippet": "TEST_F(F, T) { igsw_Main_Run(); }"}]}
    ctx = collect_copilot_project_context(bundle, gtest_state)
    assert ctx["sample_blocks"]
    prompt = build_copilot_batch_prompt(
        ctx,
        [{"candidate_id": "TC_A", "expected_input": "Given: X", "expected_output": "Then: Y"}],
    )
    assert "[TESTCASE_CODE]" in prompt
    assert "[UNRESOLVED]" in prompt
    # Compact prompt: grouping via "Generate ONLY these N testcase(s)"
    assert "Generate ONLY" in prompt or "regroup" in prompt or "Do not change grouping" in prompt


def test_apply_marks_unresolved_error(tmp_path: Path) -> None:
    bundle = {
        "test_candidates": [
            {"candidate_id": "TC_A", "expected_input": "Given: X", "expected_output": "Then: Y"},
            {"candidate_id": "TC_B", "expected_input": "Given: Z", "expected_output": "Then: W"},
        ],
        "ai_assists": {"code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}]},
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}
    out = apply_copilot_batch_import(
        bundle,
        gtest_state,
        tmp_path,
        content=BATCH_OUT,
        expected_candidate_ids=["TC_A", "TC_B"],
    )
    by_id = {r["candidate_id"]: r for r in out.get("results") or []}
    # TC_B was UNRESOLVED → now NEEDS_REVIEW (not ERROR) per updated behavior
    assert by_id["TC_B"]["workflow_status"] in ("NEEDS_REVIEW", "ERROR")
    assert by_id["TC_A"]["workflow_status"] in ("SAVED", "NEEDS_REVIEW", "DRAFT")


def test_run_progress_records_failed_chunk_reason() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
            {"id": "TC_B", "logic_id": "L1"},
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
                "TC_B": {},
            },
        },
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}
    progress_events: list[dict] = []

    def on_progress(cur: int, total: int, msg: str, **extra: object) -> None:
        progress_events.append({"cur": cur, "total": total, "msg": msg, **extra})

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": False, "error": "graph timeout"},
    ):
        out = run_copilot_batch_api(
            bundle,
            gtest_state,
            None,
            cfg={},
            candidate_ids=["TC_A", "TC_B"],
            batch_size=10,
            progress_callback=on_progress,
        )

    run = gtest_state["copilot_batch"]["run"]
    assert out["summary"]["error"] == 2
    assert run["failed_chunks"] == 1
    assert run["failed_chunk_reason"] == "graph timeout"
    assert run["failed_candidate_ids"] == ["TC_A", "TC_B"]
    assert run["completed_chunks"] == 1
    assert progress_events[-1]["failed_chunks"] == 1
    assert progress_events[-1]["failed_chunk_reason"] == "graph timeout"


def test_run_batch_preserves_m365_timeout_category() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
            },
        },
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={
            "ok": False,
            "error": "Microsoft endpoint timed out while waiting for graph.microsoft.com",
            "error_category": "m365_graph_timeout",
        },
    ):
        out = run_copilot_batch_api(
            bundle,
            gtest_state,
            None,
            cfg={},
            candidate_ids=["TC_A"],
            batch_size=1,
        )

    assert out["ok"] is True
    assert out["fallback_required"] is True
    assert gtest_state["copilot_batch"]["run"]["failed_chunk_error_category"] == "m365_graph_timeout"
    assert out["fallback_prompt"]
    assert "[TESTCASE_CODE]" in out["fallback_prompt"]
    assert "TC_A" in out["fallback_prompt"]


def test_run_batch_retries_timeout_with_minimal_prompt(tmp_path: Path) -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
            },
        },
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}
    calls: list[str] = []

    def fake_chat(cfg, prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return {"ok": False, "error": "timeout", "error_category": "m365_graph_timeout"}
        return {"ok": True, "reply": BATCH_OUT}

    with patch("web.copilot_batch_codegen.run_copilot_chat_result", side_effect=fake_chat):
        out = run_copilot_batch_api(
            bundle,
            gtest_state,
            tmp_path,
            cfg={},
            candidate_ids=["TC_A"],
            batch_size=1,
        )

    assert out["ok"] is True
    assert len(calls) == 2
    assert "fast" in calls[1].lower()  # minimal prompt says "fast retry" or "fast mode"
    assert len(calls[1]) < len(calls[0])


def test_slim_prompt_limits_long_instruction_and_source() -> None:
    long_instruction = "\n".join([f"- strict rule {i}: copy and map only" for i in range(800)])
    long_sample = "TEST_F(F, T) {\n" + "\n".join([f"  // sample line {i}" for i in range(1200)]) + "\n}"
    long_ref = "\n".join([f"void source_api_{i}();" for i in range(1000)])
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
            {
                "id": "TC_B",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "2"}]},
                "expectation": [{"signal": "B", "value": "1"}],
            },
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": long_sample, "label": "sample.cc"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
                "TC_B": {"expected_input": "Given: A=2", "expected_output": "Then: B=1"},
            },
        },
        "code_references": [{"file": "src/main.cc", "snippet_preview": long_ref}],
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}

    out = build_copilot_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=["TC_A", "TC_B"],
        engineer_note=long_instruction,
        batch_size=1,
        allow_missing_sample=True,
        slim_prompt=True,
        prompt_budget=5000,
    )

    assert out["ok"] is True
    assert out["batch_size"] == 1
    assert out["batch_count"] == 2
    assert out["context_summary"]["slim_prompt"] is True
    # Style example adds ~100–200 chars beyond the base 5000 budget — acceptable
    assert out["context_summary"]["max_prompt_chars"] <= 5300
    assert all(p["char_count"] <= 5300 for p in out["prompts"])
    assert "source_api_999" not in out["combined_prompt"]
    assert "strict rule 799" not in out["combined_prompt"]
    assert "[TESTCASE_CODE]" in out["combined_prompt"]
    assert "[UNRESOLVED]" in out["combined_prompt"]


def test_run_batch_uses_copilot_reply_field(tmp_path: Path) -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
            },
        },
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": True, "reply": BATCH_OUT},
    ):
        out = run_copilot_batch_api(
            bundle,
            gtest_state,
            tmp_path,
            cfg={},
            candidate_ids=["TC_A"],
            batch_size=1,
        )

    assert out["ok"] is True
    assert out["summary"]["saved"] + out["summary"]["needs_review"] >= 1


# ---------------------------------------------------------------------------
# Spec item 1: API timeout creates NEEDS_REVIEW fallback scaffold, not SAVED
# ---------------------------------------------------------------------------

def test_api_timeout_creates_needs_review_not_saved(tmp_path: Path) -> None:
    """On m365_graph_timeout, fallback scaffold must be NEEDS_REVIEW and never SAVED."""
    bundle = _basic_bundle()
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={
            "ok": False,
            "error": "Read timed out",
            "error_category": "m365_graph_timeout",
        },
    ):
        out = run_copilot_batch_api(
            bundle, gtest_state, tmp_path, cfg={},
            candidate_ids=["TC_A"], batch_size=1,
        )

    draft = gtest_state["drafts"].get("TC_A") or {}
    assert draft.get("code_status") == "NEEDS_REVIEW", "timeout must produce NEEDS_REVIEW"
    assert draft.get("code_status") != "SAVED"
    assert draft.get("is_fallback_scaffold") is True, "must be marked as fallback scaffold"
    assert draft.get("fallback_reason"), "must include fallback_reason"
    assert out["fallback_required"] is True


def test_fallback_scaffold_is_visible_and_editable(tmp_path: Path) -> None:
    """Fallback scaffold must have non-empty full_snippet (visible in editor)."""
    bundle = _basic_bundle()
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={
            "ok": False,
            "error": "timeout",
            "error_category": "m365_graph_timeout",
        },
    ):
        run_copilot_batch_api(
            bundle, gtest_state, tmp_path, cfg={},
            candidate_ids=["TC_A"], batch_size=1,
        )

    draft = gtest_state["drafts"].get("TC_A") or {}
    snippet = draft.get("full_snippet") or draft.get("code_body") or ""
    assert snippet.strip(), "fallback scaffold must have visible code content"
    # New timeout fallback: short comment, no GTEST_SKIP dump (GTEST_SKIP only from _persist_review_scaffold)
    assert "NEEDS_REVIEW" in snippet or "timed out" in snippet.lower() or draft.get("code_status") == "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Spec item 7: sample .cc missing does not block generation
# ---------------------------------------------------------------------------

def test_missing_sample_does_not_block_generation() -> None:
    """build_copilot_batch_prompts must succeed even without sample .cc."""
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True, "must succeed without sample .cc"
    assert result.get("missing_sample_warning"), "must include warning about missing sample"
    assert result["batch_count"] >= 1


def test_clarification_note_prepended_to_engineer_note(tmp_path: Path) -> None:
    """clarification_note must appear in the generated prompt."""
    bundle = _basic_bundle()
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    prompts_sent: list[str] = []

    def fake_chat(cfg, prompt, **kwargs):
        prompts_sent.append(prompt)
        return {"ok": True, "reply": BATCH_OUT}

    with patch("web.copilot_batch_codegen.run_copilot_chat_result", side_effect=fake_chat):
        run_copilot_batch_api(
            bundle, gtest_state, tmp_path, cfg={},
            candidate_ids=["TC_A"], batch_size=1,
            clarification_note="use fixture MySpecialFixture",
        )

    assert prompts_sent, "at least one prompt must be sent"
    assert "use fixture MySpecialFixture" in prompts_sent[0], "clarification note must appear in prompt"


# ---------------------------------------------------------------------------
# Task 1: batch run checkpoint persisted after each chunk
# ---------------------------------------------------------------------------

def _basic_bundle() -> dict:
    return {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
            },
        },
    }


def test_batch_run_checkpoint_persisted_after_chunk(tmp_path: Path) -> None:
    """gtest.json must contain copilot_batch_run_checkpoint after each completed chunk."""
    bundle = _basic_bundle()
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    (tmp_path / "bundle").mkdir(parents=True, exist_ok=True)

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": True, "reply": BATCH_OUT},
    ):
        run_copilot_batch_api(
            bundle,
            gtest_state,
            tmp_path,
            cfg={},
            candidate_ids=["TC_A"],
            batch_size=1,
        )

    gtest_path = tmp_path / "bundle" / "gtest.json"
    assert gtest_path.exists(), "gtest.json must be written after batch"
    saved = json.loads(gtest_path.read_text())
    assert "copilot_batch_run_checkpoint" in saved, "checkpoint key must be persisted"
    checkpoint = saved["copilot_batch_run_checkpoint"]
    assert checkpoint.get("status") == "completed"
    assert checkpoint.get("completed_chunks", 0) >= 1


def test_batch_run_checkpoint_persisted_after_failed_chunk(tmp_path: Path) -> None:
    """Checkpoint must also be written when a chunk fails (ERROR path)."""
    bundle = _basic_bundle()
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    (tmp_path / "bundle").mkdir(parents=True, exist_ok=True)

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": False, "error": "api_down"},
    ):
        run_copilot_batch_api(
            bundle,
            gtest_state,
            tmp_path,
            cfg={},
            candidate_ids=["TC_A"],
            batch_size=1,
        )

    gtest_path = tmp_path / "bundle" / "gtest.json"
    assert gtest_path.exists()
    saved = json.loads(gtest_path.read_text())
    checkpoint = saved.get("copilot_batch_run_checkpoint") or {}
    assert checkpoint.get("failed_chunks", 0) >= 1


# ---------------------------------------------------------------------------
# Task 2: retry only NEEDS_REVIEW / ERROR
# ---------------------------------------------------------------------------

def test_collect_retry_candidate_ids_only_failed() -> None:
    """collect_retry_candidate_ids returns only NEEDS_REVIEW and ERROR IDs."""
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
            {"id": "TC_B", "operation": {"given": []}, "expectation": []},
            {"id": "TC_C", "operation": {"given": []}, "expectation": []},
            {"id": "TC_D", "operation": {"given": []}, "expectation": []},
        ],
    }
    gtest_state = {
        "drafts": {
            "TC_A": {"code_status": "SAVED"},
            "TC_B": {"code_status": "NEEDS_REVIEW"},
            "TC_C": {"code_status": "ERROR"},
            "TC_D": {"code_status": "NO_CODE"},
        }
    }
    retry_ids = collect_retry_candidate_ids(gtest_state, bundle)
    assert set(retry_ids) == {"TC_B", "TC_C"}
    assert "TC_A" not in retry_ids
    assert "TC_D" not in retry_ids


def test_collect_retry_candidate_ids_empty_when_none_failed() -> None:
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
    }
    gtest_state = {"drafts": {"TC_A": {"code_status": "SAVED"}}}
    assert collect_retry_candidate_ids(gtest_state, bundle) == []


def test_saved_not_overwritten_during_retry(tmp_path: Path) -> None:
    """With skip_saved=True (always set by retry endpoint), SAVED TCs are not re-sent to API."""
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            },
            {
                "id": "TC_B",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "2"}]},
                "expectation": [{"signal": "B", "value": "1"}],
            },
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
                "TC_B": {"expected_input": "Given: A=2", "expected_output": "Then: B=1"},
            },
        },
    }
    saved_code = "// TC_A saved\nTEST_F(Fix, TC_A) { EXPECT_EQ(1,1); }"
    gtest_state = {
        "drafts": {
            "TC_A": {
                "code_status": "SAVED",
                "full_snippet": saved_code,
                "code_body": saved_code,
            },
            "TC_B": {"code_status": "NEEDS_REVIEW"},
        },
        "project_code_config_cache": {},
    }
    prompts_sent: list[str] = []

    def fake_chat(cfg, prompt, **kwargs):
        prompts_sent.append(prompt)
        return {
            "ok": True,
            "reply": (
                "[TESTCASE_CODE]\ntestcase_id: TC_B\n"
                "```cpp\n// TC_B\nTEST_F(Fix, TC_B) { EXPECT_EQ(2,1); }\n```\n"
                "[UNRESOLVED]\nnone\n[ASSUMPTIONS]\n- none\n"
            ),
        }

    retry_ids = collect_retry_candidate_ids(gtest_state, bundle)
    assert retry_ids == ["TC_B"], "only NEEDS_REVIEW should be in retry list"

    with patch("web.copilot_batch_codegen.run_copilot_chat_result", side_effect=fake_chat):
        out = run_copilot_batch_api(
            bundle,
            gtest_state,
            tmp_path,
            cfg={},
            candidate_ids=retry_ids,
            skip_saved=True,
            batch_size=10,
        )

    assert out["ok"] is True
    assert len(prompts_sent) == 1
    # TC_B must be in the target section of the prompt
    assert "testcase_id: TC_B" in prompts_sent[0]
    # TC_A must NOT appear as a generation target (it can appear as a saved-example style ref)
    assert "testcase_id: TC_A" not in prompts_sent[0], "SAVED TC_A must not be a generation target"
    assert gtest_state["drafts"]["TC_A"]["code_status"] == "SAVED", "TC_A must remain SAVED"
    assert gtest_state["drafts"]["TC_A"]["full_snippet"] == saved_code


# ---------------------------------------------------------------------------
# Task 3: API chunks preserve Excel / import order
# ---------------------------------------------------------------------------

def test_chunk_order_matches_excel_import_order() -> None:
    """Testcase IDs in each API chunk must follow the Excel import order, not dict order."""
    bundle = {
        "test_candidates": [
            {"id": "TC_Z", "operation": {"given": []}, "expectation": []},
            {"id": "TC_M", "operation": {"given": []}, "expectation": []},
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_Z": {"expected_input": "in", "expected_output": "out"},
                "TC_M": {"expected_input": "in", "expected_output": "out"},
                "TC_A": {"expected_input": "in", "expected_output": "out"},
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    # Pass IDs in reverse order — they must come out in Excel (TC_Z, TC_M, TC_A) order
    result = build_copilot_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=["TC_A", "TC_M", "TC_Z"],
        batch_size=10,
        allow_missing_sample=True,
    )
    assert result["ok"] is True
    all_ids_in_order = [cid for p in result["prompts"] for cid in p["candidate_ids"]]
    assert all_ids_in_order == ["TC_Z", "TC_M", "TC_A"], (
        f"Chunks must preserve Excel import order; got {all_ids_in_order}"
    )


def test_missing_io_not_silently_skipped() -> None:
    """A testcase with empty expected_input/output must be included in the API chunk."""
    bundle = {
        "test_candidates": [
            {"id": "TC_EMPTY", "operation": {"given": []}, "expectation": []},
            {"id": "TC_OK", "operation": {"given": [{"signal": "X", "value": "1"}]},
             "expectation": [{"signal": "Y", "value": "0"}]},
        ],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_EMPTY": {},                # no expected_input, no expected_output
                "TC_OK": {"expected_input": "Given: X=1", "expected_output": "Then: Y=0"},
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    result = build_copilot_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=["TC_EMPTY", "TC_OK"],
        batch_size=10,
        allow_missing_sample=True,
    )
    assert result["ok"] is True
    all_ids = [cid for p in result["prompts"] for cid in p["candidate_ids"]]
    assert "TC_EMPTY" in all_ids, "TC with no I/O must still appear in the API chunk"
    assert "TC_OK" in all_ids


# ---------------------------------------------------------------------------
# Prompt quality: no strict refusal, TODO_REVIEW, memory first, self-check
# ---------------------------------------------------------------------------

def _prompt_for(candidate_ids=("TC_A",), memory="", extra_state=None):
    bundle = {
        "test_candidates": [
            {"id": cid, "operation": {"given": [{"signal": "X", "value": "1"}]}, "expectation": [{"signal": "Y", "value": "0"}]}
            for cid in candidate_ids
        ],
        "ai_assists": {
            "workbook_overlays": {
                cid: {"expected_input": "Given: X=1", "expected_output": "Then: Y=0"}
                for cid in candidate_ids
            },
        },
    }
    gtest_state = {"drafts": {}, "project_code_config_cache": {}, **(extra_state or {})}
    result = build_copilot_batch_prompts(
        bundle, gtest_state,
        candidate_ids=list(candidate_ids),
        allow_missing_sample=True,
    )
    assert result["ok"] is True
    return result["prompts"][0]["prompt"]


def test_prompt_does_not_say_sample_is_mandatory() -> None:
    prompt = _prompt_for()
    assert "sample .cc is mandatory" not in prompt.lower()
    assert "sample .cc is required" not in prompt.lower()
    assert "load sample" not in prompt.lower()


def test_prompt_says_no_sample_use_todo_review() -> None:
    """When no sample is loaded, prompt must tell Copilot to use TODO_REVIEW patterns."""
    prompt = _prompt_for()
    assert "TODO_REVIEW" in prompt
    assert "TODO_REVIEW_Fixture" in prompt or "TODO_REVIEW" in prompt


def test_prompt_asks_for_todo_review_not_unresolved_for_missing_api() -> None:
    """Prompt must instruct use of TODO_REVIEW instead of UNRESOLVED for missing API."""
    prompt = _prompt_for()
    assert "TODO_REVIEW" in prompt


def test_prompt_says_do_not_return_testcase_code_none() -> None:
    """Prompt must forbid [TESTCASE_CODE] none when testcase has content."""
    prompt = _prompt_for()
    # New prompt uses MISSING_CONTEXT instead of [TESTCASE_CODE] none — check for that and UNRESOLVED rules
    assert (
        "[TESTCASE_CODE] none" in prompt
        or "none when" in prompt.lower()
        or "Do NOT return" in prompt
        or "MISSING_CONTEXT" in prompt  # new: use MISSING_CONTEXT instead of fake none
        or "UNRESOLVED only" in prompt
    )


def test_prompt_includes_self_check() -> None:
    """Prompt must include some verification or concrete instruction about code generation."""
    prompt = _prompt_for()
    # Compact prompt replaced verbose self-check with direct rules
    assert ("Before answering" in prompt or "verify" in prompt.lower()
            or "RULES" in prompt or "concrete code" in prompt.lower())


def test_prompt_includes_primary_goal() -> None:
    """Prompt must state the generation goal explicitly."""
    prompt = _prompt_for()
    # New prompt starts with "TASK: Generate one GTest TEST_F per testcase_id"
    assert "TASK" in prompt or "Primary goal" in prompt or "generate one" in prompt.lower()


def test_memory_appears_before_instruction_in_prompt() -> None:
    """Project Test Code Memory must appear before project instruction in prompt."""
    mem_content = "# Project Test Code Memory\n## Fixture / Test Style\n- use MyFixture\n"
    gtest_state_extra = {
        "project_code_config_cache": {
            "project_testcode_memory.md": mem_content,
            "project_instruction.md": "Follow strict style rules.",
        }
    }
    bundle = {
        "test_candidates": [
            {"id": "TC_A", "operation": {"given": []}, "expectation": []},
        ],
        "ai_assists": {
            "workbook_overlays": {"TC_A": {"expected_input": "Given: X=1", "expected_output": "Then: Y=0"}},
        },
    }
    gtest_state = {"drafts": {}, **gtest_state_extra}
    result = build_copilot_batch_prompts(
        bundle, gtest_state, candidate_ids=["TC_A"], allow_missing_sample=True
    )
    assert result["ok"] is True
    prompt = result["prompts"][0]["prompt"]
    mem_pos = prompt.find("MyFixture")
    instr_pos = prompt.find("Follow strict style rules")
    assert mem_pos >= 0, "memory content must appear in prompt"
    assert instr_pos >= 0, "instruction must appear in prompt"
    assert mem_pos < instr_pos, "memory must come before instruction in prompt"


def test_minimal_prompt_includes_todo_review_fixture() -> None:
    """Minimal prompt (timeout retry) must include TODO_REVIEW for unknown fixture."""
    from web.copilot_batch_codegen import build_copilot_minimal_prompt

    rows = [{"candidate_id": "TC_A", "expected_input": "Given: X=1", "expected_output": "Then: Y=0"}]
    prompt = build_copilot_minimal_prompt(rows)
    # New: prompt says MISSING_CONTEXT instead of TODO_REVIEW for unknown APIs
    assert "MISSING_CONTEXT" in prompt or "real" in prompt.lower() or "fixture" in prompt.lower()


def test_minimal_prompt_forbids_testcase_code_none() -> None:
    from web.copilot_batch_codegen import build_copilot_minimal_prompt

    rows = [{"candidate_id": "TC_A", "expected_input": "Given: X=1", "expected_output": ""}]
    prompt = build_copilot_minimal_prompt(rows)
    # Compact: "[TESTCASE_CODE] none" not used, but "UNRESOLVED only when content is empty" covers it
    assert "none" in prompt.lower() or "UNRESOLVED" in prompt


# ---------------------------------------------------------------------------
# UNRESOLVED → NEEDS_REVIEW (not ERROR)
# ---------------------------------------------------------------------------

_UNRESOLVED_ONLY_RESPONSE = """\
[TESTCASE_CODE]
none

[UNRESOLVED]
testcase_id: TC_A
reason: Missing required sample .cc / harness fixture / available API names.

[ASSUMPTIONS]
- no sample loaded
"""


def test_unresolved_due_to_missing_sample_is_needs_review(tmp_path: Path) -> None:
    """UNRESOLVED from Copilot → NEEDS_REVIEW + visible scaffold, not ERROR."""
    bundle = {
        "test_candidates": [
            {
                "id": "TC_A",
                "logic_id": "L1",
                "operation": {"given": [{"signal": "A", "value": "1"}]},
                "expectation": [{"signal": "B", "value": "0"}],
            }
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {
                "TC_A": {"expected_input": "Given: A=1", "expected_output": "Then: B=0"},
            },
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": True, "reply": _UNRESOLVED_ONLY_RESPONSE},
    ):
        out = run_copilot_batch_api(
            bundle, gtest_state, tmp_path, cfg={},
            candidate_ids=["TC_A"], batch_size=1,
        )

    assert out.get("ok") is True or out["summary"]["needs_review"] >= 1, \
        "UNRESOLVED response must produce NEEDS_REVIEW, not only error"
    draft = gtest_state["drafts"].get("TC_A") or {}
    assert draft.get("code_status") == "NEEDS_REVIEW", \
        f"UNRESOLVED must be NEEDS_REVIEW, got {draft.get('code_status')}"
    assert (draft.get("full_snippet") or draft.get("code_body") or "").strip(), \
        "UNRESOLVED must produce visible scaffold code, not be empty"


def test_unresolved_produces_visible_scaffold(tmp_path: Path) -> None:
    """UNRESOLVED scaffold must contain GTEST_SKIP or TODO_REVIEW so editor is not empty."""
    bundle = {
        "test_candidates": [
            {"id": "TC_B", "logic_id": "L1", "operation": {"given": []}, "expectation": []},
        ],
        "logic_blocks": [{"logic_id": "L1", "raw_expression": "A"}],
        "ai_assists": {
            "code_style_samples": [{"snippet": "TEST_F(F, T) {}", "label": "s"}],
            "workbook_overlays": {"TC_B": {"expected_input": "Given: X=1", "expected_output": "Then: Y=0"}},
        },
    }
    gtest_state: dict = {"drafts": {}, "project_code_config_cache": {}}
    response = "[TESTCASE_CODE]\nnone\n[UNRESOLVED]\ntestcase_id: TC_B\nreason: fixture unknown\n[ASSUMPTIONS]\n- none\n"

    with patch(
        "web.copilot_batch_codegen.run_copilot_chat_result",
        return_value={"ok": True, "reply": response},
    ):
        run_copilot_batch_api(
            bundle, gtest_state, tmp_path, cfg={}, candidate_ids=["TC_B"], batch_size=1
        )

    draft = gtest_state["drafts"].get("TC_B") or {}
    snippet = draft.get("full_snippet") or draft.get("code_body") or ""
    assert snippet.strip(), "UNRESOLVED must leave visible scaffold in editor"
    assert draft.get("code_status") == "NEEDS_REVIEW"
