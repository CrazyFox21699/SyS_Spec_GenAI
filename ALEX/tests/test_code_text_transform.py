"""Tests for explicit mechanical GTest / I/O text replace (no NL parsing)."""

from __future__ import annotations

from src.parsers.code_parser import import_blocks_to_draft_map, index_alex_blocks, wrap_alex_block
from web.code_text_transform import (
    apply_replace_to_bundle,
    apply_replace_to_draft,
    apply_replace_to_gtest_state,
    apply_text_replace,
    delete_drafts,
    import_monolith_to_drafts,
    merge_drafts_to_monolith,
    merge_saved_code_preview,
    preview_replace,
    wrap_draft_markers,
)


def test_wrap_alex_block_roundtrip() -> None:
    body = "// Given: X=1\nTEST_F(F, tc) { EXPECT_EQ(1, 1); }"
    marked = wrap_alex_block("TC_PM_001", body, spec_hash="abc123")
    blocks = index_alex_blocks(marked)
    assert len(blocks) == 1
    assert blocks[0]["candidate_id"] == "TC_PM_001"
    assert blocks[0]["spec_hash"] == "abc123"
    drafts = import_blocks_to_draft_map(marked)
    assert "TC_PM_001" in drafts
    assert "TEST_F(F, tc)" in drafts["TC_PM_001"]["code_body"]


def test_wrap_draft_markers() -> None:
    draft = {
        "spec_comment_block": "// Given: A=1",
        "code_body": "TEST_F(F, x) {}",
        "spec_hash": "h1",
    }
    wrapped = wrap_draft_markers("TC1", draft, spec_hash="h1")
    assert "// @alex:begin TC1" in wrapped["full_snippet"]
    assert "// @alex:spec_hash h1" in wrapped["full_snippet"]
    assert "// @alex:end TC1" in wrapped["full_snippet"]


def test_import_monolith_to_drafts() -> None:
    body = wrap_alex_block("TC2", "TEST_F(F, y) { }", spec_hash="s2")
    state = {"drafts": {}, "tc_code_index": {}}
    out = import_monolith_to_drafts(state, body)
    assert out["count"] == 1
    assert "TC2" in state["drafts"]
    assert state["tc_code_index"]["TC2"]["line_start"] == 1


def test_delete_drafts() -> None:
    state = {"drafts": {"TC1": {"full_snippet": "x"}}, "tc_code_index": {"TC1": {}}}
    out = delete_drafts(state, ["TC1"])
    assert out["count"] == 1
    assert "TC1" not in state["drafts"]


def test_merge_drafts_to_monolith() -> None:
    marked = wrap_alex_block("TC1", "TEST_F(F, a) {}", spec_hash="h")
    state = {
        "drafts": {
            "TC1": {
                "full_snippet": marked,
                "spec_hash": "h",
            }
        }
    }
    bundle = {"test_candidates": [{"id": "TC1"}], "ai_assists": {"candidate_overlays": {}}}
    text = merge_drafts_to_monolith(state, bundle, candidate_ids=["TC1"])
    assert "// @alex:begin TC1" in text
    assert "TEST_F(F, a)" in text


def test_apply_replace_to_draft() -> None:
    draft = {
        "full_snippet": "// Given: TR_ACC_RUN=ACCESSORY\nTEST_F(T, x) { /* ACCESSORY */ }",
        "spec_comment_block": "",
        "code_body": "",
    }
    updated, count = apply_replace_to_draft(
        draft,
        src="Given: TR_ACC_RUN=ACCESSORY",
        dst="Given: TR_ACC_RUN=ACC",
    )
    assert count == 1
    assert "Given: TR_ACC_RUN=ACC" in updated["full_snippet"]
    assert "ACCESSORY" in updated["full_snippet"]


def test_apply_replace_batch() -> None:
    state = {
        "drafts": {
            "TC1": {"full_snippet": "Given: A=1\nTEST_F(T, a) {}"},
            "TC2": {"full_snippet": "Given: A=1\nTEST_F(T, b) {}"},
        }
    }
    out = apply_replace_to_gtest_state(
        state,
        src="Given: A=1",
        dst="Given: A=2",
        candidate_ids=["TC1", "TC2"],
    )
    assert out["touched"] == 2
    assert out["total_replacements"] == 2
    assert "Given: A=2" in state["drafts"]["TC1"]["full_snippet"]


def test_apply_text_replace_count() -> None:
    text, n = apply_text_replace("aa bb aa", src="aa", dst="x")
    assert n == 2
    assert text == "x bb x"


def test_apply_replace_to_bundle() -> None:
    bundle = {
        "test_candidates": [{"id": "TC1"}, {"id": "TC2"}],
        "ai_assists": {
            "candidate_overlays": {
                "TC1": {"en": {"expected_input": "Given: A=OLD", "expected_output": "Then: B=1"}},
                "TC2": {"en": {"expected_input": "Given: A=OLD"}},
            }
        },
    }
    out = apply_replace_to_bundle(bundle, src="Given: A=OLD", dst="Given: A=NEW", candidate_ids=["TC1", "TC2"])
    assert out["touched"] == 2
    assert out["total_replacements"] == 2
    assert bundle["ai_assists"]["candidate_overlays"]["TC1"]["en"]["expected_input"] == "Given: A=NEW"


def test_preview_requires_explicit_from_to() -> None:
    out = preview_replace({}, {}, src="", dst="x")
    assert out["ok"] is False


def test_merge_saved_code_preview_only_saved() -> None:
    saved_block = wrap_alex_block("TC_PM_001", "TEST_F(F, a) {}", spec_hash="h1")
    draft_block = wrap_alex_block("TC_PM_002", "TEST_F(F, b) {}", spec_hash="h2")
    state = {
        "drafts": {
            "TC_PM_001": {
                "full_snippet": saved_block,
                "code_status": "SAVED",
                "spec_hash": "h1",
            },
            "TC_PM_002": {
                "full_snippet": draft_block,
                "code_status": "DRAFT",
                "spec_hash": "h2",
            },
        }
    }
    bundle = {
        "test_candidates": [{"id": "TC_PM_001"}, {"id": "TC_PM_002"}],
        "ai_assists": {"candidate_overlays": {}},
    }
    sync_map = {"TC_PM_001": "ok", "TC_PM_002": "ok"}
    out = merge_saved_code_preview(state, bundle, sync_map=sync_map)
    assert out["saved_count"] == 1
    assert out["skipped_count"] == 1
    assert "TC_PM_001" in out["included"]
    assert any(s["candidate_id"] == "TC_PM_002" and s["reason"] == "DRAFT_NOT_SAVED" for s in out["skipped"])
    assert out["total_count"] == 2
    assert "generated by ALEX" in out["content"]
    assert "TEST_F(F, a)" in out["content"]
    assert "TEST_F(F, b)" not in out["content"]


def test_merge_saved_code_dedupes_includes() -> None:
    b1 = '#include <gtest/gtest.h>\n' + wrap_alex_block("TC1", "TEST_F(F, a) {}", spec_hash="h")
    b2 = '#include <gtest/gtest.h>\n' + wrap_alex_block("TC2", "TEST_F(F, b) {}", spec_hash="h")
    state = {
        "drafts": {
            "TC1": {"full_snippet": b1, "code_status": "SAVED", "spec_hash": "h"},
            "TC2": {"full_snippet": b2, "code_status": "SAVED", "spec_hash": "h"},
        }
    }
    bundle = {"test_candidates": [{"id": "TC1"}, {"id": "TC2"}], "ai_assists": {"candidate_overlays": {}}}
    out = merge_saved_code_preview(state, bundle, sync_map={"TC1": "ok", "TC2": "ok"})
    assert out["content"].count("#include <gtest/gtest.h>") == 1


def test_merge_saved_code_skips_duplicate_identical_blocks() -> None:
    inner = "TEST_F(F, dup) { EXPECT_EQ(1, 1); }"
    b1 = wrap_alex_block("TC1", inner, spec_hash="h")
    b2 = wrap_alex_block("TC2", inner, spec_hash="h")
    state = {
        "drafts": {
            "TC1": {"full_snippet": b1, "code_status": "SAVED", "spec_hash": "h"},
            "TC2": {"full_snippet": b2, "code_status": "SAVED", "spec_hash": "h"},
        }
    }
    bundle = {"test_candidates": [{"id": "TC1"}, {"id": "TC2"}], "ai_assists": {"candidate_overlays": {}}}
    out = merge_saved_code_preview(state, bundle, sync_map={"TC1": "ok", "TC2": "ok"})
    assert out["saved_count"] == 2
    assert out["content"].count("TEST_F(F, dup)") == 1
    assert any("Duplicate identical TEST block" in w for w in out["warnings"])
