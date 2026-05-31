"""GTest code style samples — upload, bundle storage, Library, Copilot context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.parsers.code_parser import MAX_SNIPPET_CHARS, extract_test_f_blocks, infer_harness_from_code, parse_cpp_upload

MAX_CODE_SAMPLES = 3
from web.alex_storage import code_style_samples_path as alex_code_style_samples_path


def _clean_block(row: dict[str, Any], *, source_file: str = "") -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    snippet = str(row.get("snippet") or "").strip()
    test_name = str(row.get("test_name") or row.get("label") or "").strip()
    if not snippet and not test_name:
        return None
    fixture = str(row.get("fixture_class") or "").strip()
    label = str(row.get("label") or test_name or "sample").strip()[:80]
    return {
        "label": label,
        "test_name": test_name[:120],
        "fixture_class": fixture[:80],
        "source_file": str(row.get("source_file") or source_file or "")[:200],
        "snippet": snippet[:MAX_SNIPPET_CHARS],
    }


def blocks_from_code_references(code_refs: list[dict[str, Any]], *, limit: int = MAX_CODE_SAMPLES) -> list[dict[str, Any]]:
    """Turn pipeline code_references into style sample rows."""
    out: list[dict[str, Any]] = []
    for ref in code_refs or []:
        if not isinstance(ref, dict):
            continue
        source = str(ref.get("file") or ref.get("path") or "code.cpp")
        for block in ref.get("test_blocks") or []:
            cleaned = _clean_block(block, source_file=source)
            if cleaned:
                out.append(cleaned)
            if len(out) >= limit:
                return out
        if not ref.get("test_blocks") and ref.get("snippet_preview"):
            preview = str(ref["snippet_preview"]).strip()
            if preview:
                out.append(
                    {
                        "label": source,
                        "test_name": "",
                        "fixture_class": str((ref.get("harness_hints") or {}).get("fixture_class") or ""),
                        "source_file": source,
                        "snippet": preview[:MAX_SNIPPET_CHARS],
                    }
                )
            if len(out) >= limit:
                return out
    return out[:limit]


def save_code_style_samples(bundle: dict[str, Any], samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for i, row in enumerate(samples[:MAX_CODE_SAMPLES]):
        block = _clean_block(row if isinstance(row, dict) else {})
        if block:
            if not block.get("label"):
                block["label"] = f"sample_{i + 1}"
            cleaned.append(block)
    ai = bundle.setdefault("ai_assists", {})
    ai["code_style_samples"] = cleaned
    return cleaned


def load_code_style_samples(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    ai = bundle.get("ai_assists") or {}
    rows = ai.get("code_style_samples") or []
    return [r for r in rows if isinstance(r, dict) and (r.get("snippet") or r.get("test_name"))]


def merge_samples_from_bundle(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Existing uploads + auto-ingest from code_references when empty. Returns (samples, changed)."""
    existing = load_code_style_samples(bundle)
    if existing:
        return existing, False
    from_refs = blocks_from_code_references(bundle.get("code_references") or [])
    if from_refs:
        save_code_style_samples(bundle, from_refs)
        return from_refs, True
    return [], False


def code_style_reference_for_bundle(
    bundle: dict[str, Any],
    *,
    reference_test_name: str = "",
    library_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    samples = list(library_samples or []) + load_code_style_samples(bundle)
    if not samples:
        samples = blocks_from_code_references(bundle.get("code_references") or [])
    # dedupe by label
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in samples:
        key = str(row.get("label") or row.get("test_name") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    samples = unique[:MAX_CODE_SAMPLES]

    ref_name = str(reference_test_name or "").strip()
    primary: dict[str, Any] | None = None
    if ref_name:
        for row in samples:
            if str(row.get("test_name") or "") == ref_name or str(row.get("label") or "") == ref_name:
                primary = row
                break
    if primary is None and samples:
        primary = samples[0]

    return {
        "samples": samples,
        "sample_count": len(samples),
        "primary_reference": primary,
        "reference_test_name": ref_name or (primary or {}).get("test_name") or "",
    }


def apply_harness_hints(gtest_state: dict[str, Any], hints: dict[str, str]) -> dict[str, Any]:
    if not hints:
        return gtest_state
    harness = dict(gtest_state.get("harness") or {})
    for key in ("fixture_class", "inputs_member", "outputs_member", "evaluate_fn", "state_member", "state_enum"):
        if hints.get(key) and not harness.get(key):
            harness[key] = hints[key]
    if hints.get("advance_time_fn"):
        helpers = dict(harness.get("helpers") or {})
        if not helpers.get("advance_time"):
            helpers["advance_time"] = hints["advance_time_fn"]
        harness["helpers"] = helpers
    gtest_state["harness"] = harness
    return gtest_state


def ingest_cpp_upload(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    content: str,
    filename: str,
    replace: bool = False,
) -> dict[str, Any]:
    parsed = parse_cpp_upload(content, filename=filename)
    blocks = parsed.get("test_blocks") or []
    rows: list[dict[str, Any]] = []
    for block in blocks:
        cleaned = _clean_block(block, source_file=filename)
        if cleaned:
            rows.append(cleaned)
    if not rows and content.strip():
        rows.append(
            {
                "label": filename,
                "test_name": "",
                "fixture_class": str((parsed.get("harness_hints") or {}).get("fixture_class") or ""),
                "source_file": filename,
                "snippet": content.strip()[:MAX_SNIPPET_CHARS],
            }
        )
    existing = [] if replace else load_code_style_samples(bundle)
    merged = (existing + rows)[:MAX_CODE_SAMPLES]
    saved = save_code_style_samples(bundle, merged)
    apply_harness_hints(gtest_state, parsed.get("harness_hints") or {})
    return {
        "samples": saved,
        "parsed": {
            "test_block_count": len(blocks),
            "harness_hints": parsed.get("harness_hints") or {},
        },
    }


def library_code_samples_path(library_root: Path | None = None) -> Path:
    del library_root
    return alex_code_style_samples_path()


def export_library_code_samples(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "alex_code_style_samples",
        "samples": load_code_style_samples(bundle),
    }


def import_library_code_samples(bundle: dict[str, Any], preset: dict[str, Any]) -> list[dict[str, Any]]:
    rows = preset.get("samples") if isinstance(preset, dict) else None
    if not isinstance(rows, list):
        return load_code_style_samples(bundle)
    if not rows:
        return load_code_style_samples(bundle)
    existing = load_code_style_samples(bundle)
    if existing:
        return existing
    return save_code_style_samples(bundle, rows)


def validate_copilot_code_draft(draft: dict[str, Any], *, expected_test_name: str = "") -> dict[str, Any]:
    """Light quality flags for batch review UI."""
    body = str(draft.get("code_body") or draft.get("full_snippet") or "")
    return validate_gtest_code_for_save(body, candidate_id=expected_test_name)


_GTEST_BUILTINS = frozenset(
    {
        "TEST",
        "TEST_F",
        "EXPECT_EQ",
        "EXPECT_NE",
        "EXPECT_TRUE",
        "EXPECT_FALSE",
        "EXPECT_THAT",
        "ASSERT_EQ",
        "ASSERT_NE",
        "ASSERT_TRUE",
        "ASSERT_FALSE",
        "if",
        "for",
        "while",
        "switch",
        "return",
        "sizeof",
        "static_cast",
        "dynamic_cast",
        "reinterpret_cast",
        "const_cast",
    }
)


def _api_calls_from_cpp(text: str) -> set[str]:
    import re

    return {m.group(1) for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text or "")}


def validate_gtest_code_for_save(
    code: str,
    *,
    candidate_id: str = "",
    sample_snippet: str = "",
) -> dict[str, Any]:
    """Pre-save validation for Test Code workbench."""
    body = str(code or "").strip()
    flags: list[str] = []
    warnings: list[str] = []

    if not body:
        flags.append("empty")
    if "```" in body:
        flags.append("markdown_fence")
    if re.search(r"\bTODO\b", body, re.IGNORECASE):
        flags.append("todo")
    if not re.search(r"\bTEST(?:_F)?\s*\(", body):
        flags.append("missing_TEST")
    if not re_search_expect(body) and not re.search(r"\bASSERT_(EQ|NE|TRUE|FALSE|THAT)\b", body):
        flags.append("missing_EXPECT")
    cid = str(candidate_id or "").strip()
    if cid and cid not in body:
        flags.append("missing_candidate_id_comment")

    if sample_snippet.strip():
        sample_apis = _api_calls_from_cpp(sample_snippet) - _GTEST_BUILTINS
        code_apis = _api_calls_from_cpp(body) - _GTEST_BUILTINS
        unknown = sorted(code_apis - sample_apis)
        unknown = [u for u in unknown if len(u) > 2 and not u.startswith("EXPECT") and not u.startswith("ASSERT")]
        if unknown:
            warnings.append(f"unknown_api_vs_sample: {', '.join(unknown[:8])}")

    hard_fail = {"empty", "markdown_fence", "missing_TEST", "missing_EXPECT"}
    ok = not (hard_fail & set(flags))
    user_action = None
    if "missing_candidate_id_comment" in flags:
        user_action = f"Add // {cid} in spec comment block before saving."
    elif "markdown_fence" in flags:
        user_action = "Remove markdown ``` fences — save C++ only."
    elif "todo" in flags:
        user_action = "Resolve TODO comments before saving."

    quality = "good" if ok and not flags and not warnings else ("review" if ok else "failed")
    return {
        "ok": ok,
        "flags": flags,
        "warnings": warnings,
        "quality": quality,
        "user_action": user_action,
    }


def re_search_expect(text: str) -> bool:
    import re

    return bool(re.search(r"\bEXPECT_(EQ|NE|TRUE|FALSE|THAT)\b", text))
