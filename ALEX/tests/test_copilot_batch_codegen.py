"""Copilot batch orchestrator — prompt, parse, import."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from web.copilot_batch_codegen import (
    apply_copilot_batch_import,
    build_copilot_batch_prompts,
    collect_copilot_project_context,
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
    assert "Do not change grouping" in prompt


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
    assert by_id["TC_B"]["workflow_status"] == "ERROR"
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

    assert out["ok"] is False
    assert out["error_category"] == "m365_graph_timeout"
    assert gtest_state["copilot_batch"]["run"]["failed_chunk_error_category"] == "m365_graph_timeout"
    assert out["fallback_prompt"]
    assert "Fast mode" in out["fallback_prompt"]


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
    assert "Fast mode" in calls[1]
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
    assert out["context_summary"]["max_prompt_chars"] <= 5000
    assert all(p["char_count"] <= 5000 for p in out["prompts"])
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
