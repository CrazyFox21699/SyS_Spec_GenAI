"""Tests for Copilot GTest code writer (mocked M365)."""

from __future__ import annotations

import textwrap
from unittest.mock import patch

from web.code_style_samples import validate_gtest_code_for_save
from web.copilot_code_writer import (
    _extract_given_when,
    build_gtest_copilot_prompt,
    build_gtest_copilot_prompt_followup,
    normalize_testf_snippet,
    parse_copilot_cpp_response,
    run_code_write,
    sanitize_generated_cpp_body,
)
from web.project_testcode_memory import get_mapped_output_signals, parse_condition_code_entries


def _minimal_pack() -> dict:
    return {
        "testcase": {
            "candidate_id": "TC_PM_004",
            "expected_input": "Given: A=1",
            "expected_output": "Then: B=0",
        },
        "harness": {"fixture_class": "T"},
        "io_variable_map": {},
        "verification_patterns": [],
        "sibling_assertions": [],
        "logic": {},
        "baseline_skeleton": {},
        "code_style_reference": {"samples": [{"label": "ref", "snippet": "TEST_F(T, x) { RunForMs(10); }"}]},
    }


def test_run_code_write_parses_json_legacy() -> None:
    pack = _minimal_pack()
    reply = '{"test_name": "TC1_test", "code_body": "TEST_F(T, TC1_test) { EXPECT_EQ(a,1); }", "full_snippet": "// TC_PM_004\\nTEST_F(T, TC1_test) { EXPECT_EQ(a,1); }"}'
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        out = run_code_write(pack, {})
    assert out["ok"] is True
    assert "TC1_test" in out["draft"]["full_snippet"]


def test_run_code_write_parses_cpp_fence() -> None:
    pack = _minimal_pack()
    reply = """```cpp
// TC_PM_004
TEST_F(T, my_test) {
  EXPECT_EQ(out.B, 0);
}
```
ASSUMPTIONS:
- Used RunForMs from sample
"""
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        out = run_code_write(pack, {})
    assert out["ok"] is True
    assert "TC_PM_004" in out["draft"]["full_snippet"]
    assert "EXPECT_EQ" in out["draft"]["full_snippet"]


def test_parse_copilot_cpp_response() -> None:
    text = "```cpp\nTEST_F(F, t) { EXPECT_TRUE(x); }\n```\nASSUMPTIONS:\n- ok\n"
    parsed = parse_copilot_cpp_response(text)
    assert "TEST_F" in parsed["full_snippet"]
    assert parsed["assumptions"] == ["ok"]


def test_build_gtest_copilot_prompt_includes_rules() -> None:
    prompt = build_gtest_copilot_prompt(_minimal_pack(), code_rule="Use RunForMs after When")
    assert "Code Rule / Change Request" in prompt
    assert "TC_PM_004" in prompt
    assert "Generate GTest C++ ONLY" in prompt


def test_followup_prompt_shorter_than_full() -> None:
    pack = _minimal_pack()
    full = build_gtest_copilot_prompt(pack, slim=True)
    follow = build_gtest_copilot_prompt_followup(pack, code_rule="Use RunForMs")
    assert len(follow) < len(full)
    assert "TC_PM_004" in follow
    assert "Same GTest style" in follow


def test_validate_gtest_code_for_save() -> None:
    code = "// TC_PM_004\nTEST_F(T, x) { EXPECT_EQ(a, 1); }"
    val = validate_gtest_code_for_save(code, candidate_id="TC_PM_004", sample_snippet="TEST_F(T,x){RunForMs(1);}")
    assert val["ok"] is True


def test_run_code_refine_accepts_skeleton_without_expect() -> None:
    existing = "// TC_PM_008\nTEST_F(T, t) { /* Then: OUT=1 */ }"
    reply = """```cpp
// TC_PM_008
TEST_F(T, t) {
  // Then: RELAY_MAIN=OFF
}
```"""
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={"ok": True, "reply": reply},
    ):
        from web.copilot_code_writer import run_code_refine

        out = run_code_refine(existing, "convert SHUT_OFF line", {})
    assert out["ok"] is True
    assert "RELAY_MAIN" in out["draft"]["full_snippet"]
    assert "missing_EXPECT" in (out.get("validation") or {}).get("flags", [])


def test_run_code_write_returns_structured_error() -> None:
    pack = _minimal_pack()
    with patch(
        "web.copilot_code_writer.run_copilot_chat_result",
        return_value={
            "ok": False,
            "error": "no license",
            "error_category": "m365_not_entitled",
            "graph_status": 403,
        },
    ):
        out = run_code_write(pack, {})
    assert out["ok"] is False
    assert out["error_category"] == "m365_not_entitled"


# ---------------------------------------------------------------------------
# Draft generation policy: When-action and EXPECT_CALL/EXPECT_THAT safety
# ---------------------------------------------------------------------------


def _snippet_with_block(testcase_id: str, fixture: str, body_lines: str) -> str:
    """Build a minimal snippet with a block comment so normalize_testf_snippet activates."""
    return textwrap.dedent(f"""\
        /*
         * testcase_id: {testcase_id}
         * event: SomeEvent
         * Given: SIG=0
         */
        TEST_F({fixture}, {testcase_id})
        {{
        {body_lines}
        }}
    """)


def test_no_main_call_when_testspec_has_no_when() -> None:
    """igsw_Main_Run must not appear when testspec has no explicit When action."""
    snippet = _snippet_with_block(
        "TC_IMP_006",
        "TryToEvaluateNok",
        "    // When: evaluate NOK state\n    igsw_Main_Run();\n    // ALEX_REVIEW: output mapping missing for NOK_SHUTOFF",
    )
    row = {
        "candidate_id": "TC_IMP_006",
        "event": "Evaluate NOK",
        "expected_input": "Given: NOK_SHUTOFF=0",  # no When: in expected_input
        "expected_output": "Then: NOK_SHUTOFF=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "igsw_Main_Run" not in result, "igsw_Main_Run must be absent when testspec has no explicit When"
    assert "// When: no explicit action in testspec" in result


def test_operation_column_does_not_generate_main_call() -> None:
    """Operation/namespace text must not be treated as an executable When trigger."""
    snippet = _snippet_with_block(
        "TC_IMP_007",
        "TryToPowerAccident",
        "    - Main function call: igsw_Main_Run()\n    EXPECT_THAT(PWR_STATE, Eq(1u));",
    )
    row = {
        "candidate_id": "TC_IMP_007",
        "event": "PowerAccident",
        "expected_input": "Given: PWR_STATE=0",  # no When: — operation column only
        "expected_output": "Then: PWR_STATE=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "igsw_Main_Run" not in result, "igsw_Main_Run from bullet must be removed without explicit When"
    # Bullet should not survive as '- ' line
    for line in result.splitlines():
        assert not line.lstrip().startswith("- "), f"Markdown bullet still present: {line!r}"


def test_missing_input_mapping_does_not_emit_partial_expect_call() -> None:
    """Incomplete EXPECT_CALL blocks must be replaced with an ALEX_REVIEW comment."""
    body = (
        "\n"
        "    EXPECT_CALL(rte,\n"
        "    .WillRepeatedly(DoAll(SetArgPointee<0>(1u),\n"
        "    // ALEX_REVIEW: input mapping missing for SIG\n"
        "}\n"
    )
    result = sanitize_generated_cpp_body(body, has_explicit_when=False)
    assert "EXPECT_CALL(rte," not in result, "Incomplete EXPECT_CALL must be removed"
    assert ".WillRepeatedly" not in result, "Orphaned chained call must be removed"
    assert "ALEX_REVIEW" in result
    assert "incomplete EXPECT_CALL removed" in result or "input mapping missing" in result


def test_missing_output_mapping_does_not_emit_raw_expect_that() -> None:
    """Incomplete EXPECT_THAT blocks must be replaced with an ALEX_REVIEW comment."""
    body = (
        "\n"
        "    EXPECT_THAT(\n"
        "        UnknownSignal,\n"
        "    // no mapping known\n"
        "}\n"
    )
    result = sanitize_generated_cpp_body(body, has_explicit_when=False)
    assert "EXPECT_THAT(" not in result, "Incomplete EXPECT_THAT must be removed"
    assert "ALEX_REVIEW" in result
    assert "incomplete EXPECT_THAT removed" in result or "output mapping" in result


def test_no_markdown_bullet_lines_in_cpp_body() -> None:
    """No '- ' bullet lines must survive sanitization; igsw_Main_Run bullets are removed."""
    body = (
        "\n"
        "    // Given: SIG=0\n"
        "    - Main function call: igsw_Main_Run()\n"
        "    - Some note about setup\n"
        "    EXPECT_THAT(V_OUT, Eq(0u));\n"
        "}\n"
    )
    result = sanitize_generated_cpp_body(body, has_explicit_when=False)
    for line in result.splitlines():
        assert not line.lstrip().startswith("- "), f"Markdown bullet still present: {line!r}"
    # igsw_Main_Run bullet removed entirely (not converted to comment)
    assert "igsw_Main_Run" not in result
    # Non-main bullet converted to C++ comment
    assert "// Some note about setup" in result
    # Rule 5: EXPECT_THAT with raw ALL_CAPS signal (V_OUT) is replaced with ALEX_REVIEW
    assert "EXPECT_THAT(V_OUT" not in result
    assert "ALEX_REVIEW" in result
    assert "V_OUT" in result  # signal name should still appear in the ALEX_REVIEW comment


# ---------------------------------------------------------------------------
# Generation path coverage: all paths must run the sanitizer
# ---------------------------------------------------------------------------


def _snippet_no_block_comment(fixture: str, cid: str, body_lines: str) -> str:
    """Snippet without a block comment — exercises the no-block-comment sanitizer path."""
    return f"TEST_F({fixture}, {cid})\n{{\n{body_lines}\n}}\n"


def test_all_generation_paths_strip_main_function_bullet() -> None:
    """Bullet '- Main function call:' must be removed even when there is no block comment.

    TC_IMP_006 bad output had no block comment, so normalize_testf_snippet previously
    returned early.  The sanitizer must now apply unconditionally.
    """
    snippet = _snippet_no_block_comment(
        "TryToEvaluateNok",
        "TC_IMP_006",
        "    // Given: no explicit input condition in testspec\n"
        "    - Main function call: igsw_Main_Run()\n"
        "    // ALEX_REVIEW: output mapping missing for NOK_SHUTOFF",
    )
    row = {
        "candidate_id": "TC_IMP_006",
        "event": "Evaluate NOK",
        "expected_input": "Given: NOK_SHUTOFF=0",
        "expected_output": "Then: NOK_SHUTOFF=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "- Main function call" not in result, "Markdown bullet must not survive"
    assert "igsw_Main_Run" not in result, "igsw_Main_Run must be removed without explicit When"
    for line in result.splitlines():
        assert not line.lstrip().startswith("- "), f"Bullet line still present: {line!r}"


def test_review_draft_path_runs_sanitizer() -> None:
    """normalize_testf_snippet applied to _build_review_draft output must strip bullets.

    Simulates the LOCAL_REVIEW_DRAFT path where project memory contained a bullet-format
    'Main function call: igsw_Main_Run()' pattern.
    """
    # Mimic the _build_review_draft format: block comment + TEST_F + body with bullet
    draft_snippet = textwrap.dedent("""\
        /*
         * testcase_id: TC_IMP_006
         * event: Evaluate NOK
         * Given: NOK_SHUTOFF=0
         * Then: NOK_SHUTOFF=1
         */
        TEST_F(TryToEvaluateNok, TC_IMP_006)
        {
            // Given: no explicit input condition in testspec
            - Main function call: igsw_Main_Run()
            // ALEX_REVIEW: output mapping missing for NOK_SHUTOFF
        }
    """)
    row = {
        "candidate_id": "TC_IMP_006",
        "event": "Evaluate NOK",
        "expected_input": "Given: NOK_SHUTOFF=0",
        "expected_output": "Then: NOK_SHUTOFF=1",
    }
    result = normalize_testf_snippet(draft_snippet, row)
    assert "- Main function call" not in result
    assert "igsw_Main_Run" not in result
    assert "ALEX_REVIEW" in result  # output mapping comment preserved


def test_embedded_when_text_split_from_expected_input() -> None:
    """'Given: A = 1. When: B = ON' must split into given='A = 1', when='B = ON'."""
    given, when = _extract_given_when("Given: WMODE_CMD = 1. When: PWR_STATE = ON")
    assert given == "WMODE_CMD = 1", f"Given should be 'WMODE_CMD = 1', got {given!r}"
    assert when == "PWR_STATE = ON", f"When should be 'PWR_STATE = ON', got {when!r}"


def test_embedded_when_split_produces_correct_block_comment() -> None:
    """After split, block comment shows Given: WMODE_CMD = 1 and When: PWR_STATE = ON separately."""
    snippet = _snippet_with_block(
        "TC_IMP_007",
        "TryToPowerAccidentHappend",
        "    // Given:\n    // When:\n    igsw_Main_Run();",
    )
    row = {
        "candidate_id": "TC_IMP_007",
        "event": "PowerAccident",
        "expected_input": "Given: WMODE_CMD = 1. When: PWR_STATE = ON",
        "expected_output": "Then: PWR_STATE = 1",
    }
    result = normalize_testf_snippet(snippet, row)
    # Given in block comment must NOT include "When: PWR_STATE = ON"
    assert "WMODE_CMD = 1. When: PWR_STATE = ON" not in result, (
        "Embedded When must be split — should not appear verbatim in Given"
    )
    # igsw_Main_Run removed (When text 'PWR_STATE = ON' is not executable)
    assert "igsw_Main_Run" not in result
    # ALEX_REVIEW for non-executable When condition must appear
    assert "no executable action mapping for When condition" in result


def test_raw_output_signal_does_not_generate_expect_that_without_mapping() -> None:
    """EXPECT_THAT with a raw ALL_CAPS signal name must be replaced with ALEX_REVIEW."""
    body = (
        "\n"
        "    // Then: PWR_STATE = 1\n"
        "    EXPECT_THAT(PWR_STATE, Eq(1u));\n"
        "}\n"
    )
    result = sanitize_generated_cpp_body(body, has_explicit_when=True)
    assert "EXPECT_THAT(PWR_STATE" not in result, "Raw signal EXPECT_THAT must be removed"
    assert "ALEX_REVIEW" in result
    assert "PWR_STATE" in result  # signal name preserved in comment
    # Valid lowercase EXPECT_THAT must NOT be touched
    body2 = "\n    EXPECT_THAT(result.speed, Eq(100));\n}\n"
    result2 = sanitize_generated_cpp_body(body2, has_explicit_when=True)
    assert "EXPECT_THAT(result.speed, Eq(100))" in result2


def test_incomplete_expect_call_removed_from_all_paths() -> None:
    """Incomplete EXPECT_CALL must be removed even when snippet has no block comment."""
    snippet = _snippet_no_block_comment(
        "TryToPowerAccidentHappend",
        "TC_IMP_007",
        "    EXPECT_CALL(rte,\n"
        "    .WillRepeatedly(DoAll(SetArgPointee<0>(1u),\n"
        "    EXPECT_THAT(PWR_STATE, Eq(1u));\n"
        "    // ALEX_REVIEW: input mapping missing for PWR_STATE",
    )
    row = {
        "candidate_id": "TC_IMP_007",
        "expected_input": "Given: PWR_STATE=0",
        "expected_output": "Then: PWR_STATE=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "EXPECT_CALL(rte," not in result, "Incomplete EXPECT_CALL must be removed"
    assert ".WillRepeatedly" not in result, "Orphaned chain must be removed"
    # Raw signal EXPECT_THAT also removed (Rule 5)
    assert "EXPECT_THAT(PWR_STATE" not in result
    assert "ALEX_REVIEW" in result


def test_operation_column_never_generates_igsw_main_run() -> None:
    """igsw_Main_Run must be absent whether it comes via bullet or bare call, without explicit When."""
    # Bullet form (from project memory)
    body_bullet = "\n    - Main function call: igsw_Main_Run()\n}\n"
    r1 = sanitize_generated_cpp_body(body_bullet, has_explicit_when=False)
    assert "igsw_Main_Run" not in r1

    # Bare call form
    body_call = "\n    igsw_Main_Run();\n}\n"
    r2 = sanitize_generated_cpp_body(body_call, has_explicit_when=False)
    assert "igsw_Main_Run" not in r2

    # When has_explicit_when=True (executable), must be kept
    body_kept = "\n    igsw_Main_Run();\n}\n"
    r3 = sanitize_generated_cpp_body(body_kept, has_explicit_when=True)
    assert "igsw_Main_Run" in r3


# Task 22: When-source tracking — igsw_Main_Run must only appear if testspec explicitly requests it
# -------------------------------------------------------------------------------------------------


def test_memory_main_call_does_not_create_when_action() -> None:
    """sanitize Rule 7: // When: igsw_Main_Run() comment without testspec auth → placeholder."""
    body = "    // When: igsw_Main_Run()\n    // Then: something\n"
    result = sanitize_generated_cpp_body(body, has_explicit_when=False)
    assert "igsw_Main_Run" not in result
    assert "// When: no explicit action in testspec" in result
    # Then comment must survive unchanged
    assert "// Then: something" in result


def test_style_example_main_call_does_not_create_when_action() -> None:
    """Copilot body // When: igsw_Main_Run() from style example is replaced when row has no When."""
    snippet = _snippet_with_block(
        "TC_IMP_008",
        "TryToEvalMode",
        "    // When: igsw_Main_Run()\n    // Then: OUT=1",
    )
    row = {
        "candidate_id": "TC_IMP_008",
        "event": "EvalMode",
        "expected_input": "Given: SIG=0",  # no When: field
        "expected_output": "Then: OUT=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "igsw_Main_Run" not in result
    assert "// When: no explicit action in testspec" in result


def test_default_template_main_call_removed_if_not_in_testspec() -> None:
    """Default template // When: igsw_Main_Run()\nigsw_Main_Run(); block is removed when no testspec When."""
    snippet = _snippet_with_block(
        "TC_IMP_009",
        "TryToDefaultMode",
        "    // When: igsw_Main_Run()\n    igsw_Main_Run();\n    // Then: STS=1",
    )
    row = {
        "candidate_id": "TC_IMP_009",
        "event": "DefaultMode",
        "expected_input": "Given: SIG=1",
        "expected_output": "Then: STS=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "igsw_Main_Run" not in result
    assert "// When: no explicit action in testspec" in result


def test_explicit_testspec_when_condition_preserved_not_replaced_by_main() -> None:
    """TC_IMP_007 scenario: testspec When='PWR_STATE = ON' must replace Copilot // When: igsw_Main_Run()."""
    snippet = _snippet_with_block(
        "TC_IMP_007",
        "TryToPowerAccidentHappend",
        "    // When: igsw_Main_Run()\n    igsw_Main_Run();\n    // Then: PWR_STATE=1",
    )
    row = {
        "candidate_id": "TC_IMP_007",
        "event": "PowerAccident",
        "expected_input": "Given: WMODE_CMD = 1. When: PWR_STATE = ON",
        "expected_output": "Then: PWR_STATE=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "igsw_Main_Run" not in result, "igsw_Main_Run must not appear — testspec When is a condition, not a call"
    assert "// When: PWR_STATE = ON" in result
    assert "ALEX_REVIEW: no executable action mapping" in result
    assert "When condition: PWR_STATE = ON" in result


def test_operation_column_when_field_not_authoritative() -> None:
    """Block-comment when: igsw_Main_Run() derived from operation column must be cleared when row has no When."""
    snippet = textwrap.dedent("""\
        /*
         * testcase_id: TC_IMP_010
         * event: EvalNok
         * Given: SIG=0
         * when: igsw_Main_Run()
         */
        TEST_F(TryToEvalNok, TC_IMP_010)
        {
            // When: igsw_Main_Run()
            igsw_Main_Run();
        }
    """)
    row = {
        "candidate_id": "TC_IMP_010",
        "event": "EvalNok",
        "expected_input": "Given: SIG=0",  # no When: — operation only
        "expected_output": "Then: OUT=1",
    }
    result = normalize_testf_snippet(snippet, row)
    assert "igsw_Main_Run" not in result
    assert "// When: no explicit action in testspec" in result


def test_final_sanitizer_removes_when_igsw_main_if_not_testspec_source() -> None:
    """Rule 7: sanitizer replaces // When: igsw_Main_Run() with placeholder when has_explicit_when=False."""
    # Comment-only form (no bare call)
    body = "    // When: igsw_Main_Run()\n    EXPECT_CALL(rte, Foo(NotNull()));\n"
    result = sanitize_generated_cpp_body(body, has_explicit_when=False)
    assert "// When: no explicit action in testspec" in result
    assert "igsw_Main_Run" not in result
    # EXPECT_CALL must survive
    assert "EXPECT_CALL" in result

    # With executable When (has_explicit_when=True) the comment is NOT replaced
    body2 = "    // When: igsw_Main_Run()\n"
    result2 = sanitize_generated_cpp_body(body2, has_explicit_when=True)
    assert "// When: igsw_Main_Run()" in result2


# Task 23: Output mapping — memory-mapped EXPECT_THAT must not be replaced with ALEX_REVIEW
# ------------------------------------------------------------------------------------------

_PWR_MEMORY = textwrap.dedent("""\
    ## Output Assertion Pattern

    * condition: PWR_STATE = 1
      code: |
        EXPECT_THAT(PWR_STATE, Eq(1u));
""")


def test_mapped_all_caps_output_is_preserved() -> None:
    """sanitizer Rule 5 is skipped when signal has an explicit condition/code entry in memory."""
    body = "    EXPECT_THAT(PWR_STATE, Eq(1u));\n"
    mapped = frozenset({"PWR_STATE"})
    result = sanitize_generated_cpp_body(body, mapped_output_signals=mapped)
    assert "EXPECT_THAT(PWR_STATE, Eq(1u))" in result
    assert "ALEX_REVIEW" not in result


def test_pwr_state_equals_1_memory_mapping_generates_expect_that() -> None:
    """TC_IMP_007: memory condition 'PWR_STATE = 1' preserves EXPECT_THAT through normalize."""
    snippet = _snippet_with_block(
        "TC_IMP_007",
        "TryToPowerAccidentHappend",
        "    // Then: PWR_STATE = 1\n    EXPECT_THAT(PWR_STATE, Eq(1u));",
    )
    row = {
        "candidate_id": "TC_IMP_007",
        "event": "PowerAccident",
        "expected_input": "Given: WMODE_CMD = 1",
        "expected_output": "Then: PWR_STATE = 1",
    }
    result = normalize_testf_snippet(snippet, row, memory_content=_PWR_MEMORY)
    assert "EXPECT_THAT(PWR_STATE, Eq(1u))" in result
    assert "ALEX_REVIEW" not in result


def test_all_caps_raw_expect_that_without_mapping_is_replaced() -> None:
    """Rule 5 still replaces EXPECT_THAT(ALL_CAPS, ...) when signal has no memory mapping."""
    body = "    EXPECT_THAT(UNMAPPED_SIG, Eq(0u));\n"
    result = sanitize_generated_cpp_body(body, mapped_output_signals=frozenset())
    # The original call must be gone; ALEX_REVIEW comment replaces it
    assert "EXPECT_THAT(UNMAPPED_SIG" not in result
    assert "ALEX_REVIEW: output mapping missing for UNMAPPED_SIG" in result


def test_output_mapping_normalizes_spaces() -> None:
    """Spaces around = in condition/expected_output are normalised before matching."""
    memory_no_spaces = textwrap.dedent("""\
        ## Output Assertion Pattern

        * condition: SIG=2
          code: |
            EXPECT_THAT(SIG, Eq(2u));
    """)
    # expected_output has spaces: "SIG = 2"
    mapped = get_mapped_output_signals(memory_no_spaces, "Then: SIG = 2")
    assert "SIG" in mapped

    # Also test the reverse (memory has spaces, eo has no spaces)
    memory_with_spaces = textwrap.dedent("""\
        ## Output Assertion Pattern

        * condition: SIG = 2
          code: |
            EXPECT_THAT(SIG, Eq(2u));
    """)
    mapped2 = get_mapped_output_signals(memory_with_spaces, "Then: SIG=2")
    assert "SIG" in mapped2


def test_project_memory_condition_code_pipe_format_is_parsed() -> None:
    """Inline pipe format '- condition: X code: | Y notes:' is parsed correctly."""
    section_body = (
        "- condition: PWR_STATE = 1 code: | EXPECT_THAT(PWR_STATE, Eq(1u)); notes: direct read"
    )
    entries = parse_condition_code_entries(section_body)
    assert len(entries) == 1
    e = entries[0]
    assert e["signal"] == "PWR_STATE"
    assert e["value"] == "1"
    assert "EXPECT_THAT(PWR_STATE, Eq(1u));" in e["code"]
