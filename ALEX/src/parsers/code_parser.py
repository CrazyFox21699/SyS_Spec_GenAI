"""Source / GTest code hints and style-sample extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MAX_SNIPPET_CHARS = 10_000
MAX_TEST_BLOCKS = 8


def scan_code_hints(path: Path) -> dict[str, bool | list[str] | str | None]:
    text = path.read_text(encoding="utf-8", errors="replace")[:100000]
    fixture_class = None
    m = re.search(r"class\s+(\w+)\s*:\s*public\s+::testing::Test", text)
    if m:
        fixture_class = m.group(1)
    hints = {
        "has_gtest": bool(re.search(r"\bTEST_F\s*\(", text)),
        "has_expect": bool(re.search(r"\bEXPECT_(EQ|NE|TRUE|FALSE)", text)),
        "has_assert": bool(re.search(r"\bASSERT_(EQ|NE|TRUE|FALSE)", text)),
        "macro_hits": [],
        "fixture_class": fixture_class,
    }
    for m in re.finditer(r"\b(TEST_F|EXPECT_EQ|ASSERT_EQ)\b", text):
        if m.group(0) not in hints["macro_hits"]:
            hints["macro_hits"].append(m.group(0))
    return hints  # type: ignore[return-value]


def extract_test_f_blocks(text: str, *, max_blocks: int = MAX_TEST_BLOCKS) -> list[dict[str, Any]]:
    """Extract TEST_F blocks with balanced braces."""
    blocks: list[dict[str, Any]] = []
    pattern = re.compile(
        r"\bTEST_F\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*\{",
        re.MULTILINE,
    )
    for m in pattern.finditer(text[:200_000]):
        fixture = m.group(1)
        test_name = m.group(2)
        start = m.start()
        brace_start = text.find("{", m.end() - 1)
        if brace_start < 0:
            continue
        depth = 0
        end = brace_start
        for i in range(brace_start, min(len(text), brace_start + 20_000)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        snippet = text[start:end].strip()
        if len(snippet) > MAX_SNIPPET_CHARS:
            snippet = snippet[:MAX_SNIPPET_CHARS] + "\n// … truncated …"
        blocks.append(
            {
                "fixture_class": fixture,
                "test_name": test_name,
                "snippet": snippet,
                "label": f"{fixture}.{test_name}",
            }
        )
        if len(blocks) >= max_blocks:
            break
    return blocks


def infer_harness_from_code(text: str) -> dict[str, str]:
    """Best-effort harness hints from C++ sample (fixture, in/out members, helpers)."""
    hints: dict[str, str] = {}
    m = re.search(r"class\s+(\w+)\s*:\s*public\s+::testing::Test", text)
    if m:
        hints["fixture_class"] = m.group(1)
    blocks = extract_test_f_blocks(text, max_blocks=3)
    if blocks and not hints.get("fixture_class"):
        hints["fixture_class"] = blocks[0].get("fixture_class") or ""

    member_hits: dict[str, int] = {}
    for m in re.finditer(r"\b(in|out|inputs|outputs|input|output)\s*\.\s*([A-Za-z_]\w*)", text[:80_000]):
        member = m.group(1)
        member_hits[member] = member_hits.get(member, 0) + 1
    if member_hits.get("in", 0) + member_hits.get("inputs", 0) + member_hits.get("input", 0) > 0:
        hints["inputs_member"] = "in" if member_hits.get("in") else "inputs"
    if member_hits.get("out", 0) + member_hits.get("outputs", 0) + member_hits.get("output", 0) > 0:
        hints["outputs_member"] = "out" if member_hits.get("out") else "outputs"

    for fn in ("RunForMs", "AdvanceTime", "EvaluatePowerMode", "Evaluate"):
        if re.search(rf"\b{re.escape(fn)}\s*\(", text):
            if fn in ("RunForMs", "AdvanceTime"):
                hints.setdefault("advance_time_fn", fn)
            else:
                hints.setdefault("evaluate_fn", fn)
    return hints


def extract_code_reference(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    hints = scan_code_hints(path)
    test_blocks = extract_test_f_blocks(text)
    harness_hints = infer_harness_from_code(text)
    return {
        "file": path.name,
        "path": str(path),
        "length_chars": len(text),
        "hints": hints,
        "test_blocks": test_blocks,
        "harness_hints": harness_hints,
        "snippet_preview": test_blocks[0]["snippet"][:2000] if test_blocks else text[:1500],
    }


def parse_cpp_upload(content: str, *, filename: str = "upload.cpp") -> dict[str, Any]:
    """Parse uploaded C++ for code-style samples (API / UI attach)."""
    text = str(content or "")[:250_000]
    test_blocks = extract_test_f_blocks(text)
    harness_hints = infer_harness_from_code(text)
    hints = {
        "has_gtest": bool(re.search(r"\bTEST_F\s*\(", text)),
        "fixture_class": harness_hints.get("fixture_class"),
    }
    return {
        "file": filename,
        "length_chars": len(text),
        "hints": hints,
        "test_blocks": test_blocks,
        "harness_hints": harness_hints,
    }


ALEX_BEGIN_RE = re.compile(r"^\s*//\s*@alex:begin\s+(\S+)", re.MULTILINE)
ALEX_END_RE = re.compile(r"^\s*//\s*@alex:end\s+(\S+)", re.MULTILINE)
ALEX_SPEC_HASH_RE = re.compile(r"^\s*//\s*@alex:spec_hash\s+(\S+)", re.MULTILINE)


def wrap_alex_block(candidate_id: str, body: str, *, spec_hash: str = "") -> str:
    cid = str(candidate_id or "").strip()
    inner = str(body or "").strip()
    lines = [f"// @alex:begin {cid}"]
    if spec_hash:
        lines.append(f"// @alex:spec_hash {spec_hash}")
    lines.append(inner)
    lines.append(f"// @alex:end {cid}")
    return "\n".join(lines)


def index_alex_blocks(text: str) -> list[dict[str, Any]]:
    """Scan full monolith for @alex begin/end pairs (line-based, no size cap)."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    blocks: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        m = ALEX_BEGIN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        cid = m.group(1)
        start = i
        i += 1
        spec_hash = ""
        while i < len(lines):
            hm = ALEX_SPEC_HASH_RE.match(lines[i])
            if hm:
                spec_hash = hm.group(1)
                i += 1
                continue
            em = ALEX_END_RE.match(lines[i])
            if em and em.group(1) == cid:
                end = i
                snippet = "\n".join(lines[start : end + 1]).strip()
                blocks.append(
                    {
                        "candidate_id": cid,
                        "line_start": start + 1,
                        "line_end": end + 1,
                        "spec_hash": spec_hash,
                        "snippet": snippet,
                    }
                )
                i += 1
                break
            i += 1
    return blocks


def import_blocks_to_draft_map(text: str) -> dict[str, dict[str, Any]]:
    """Map candidate_id → draft payload from marked monolith."""
    out: dict[str, dict[str, Any]] = {}
    for block in index_alex_blocks(text):
        cid = block["candidate_id"]
        snippet = block["snippet"]
        body_start = snippet.find("TEST_F(")
        if body_start < 0:
            body_start = len(snippet)
        spec_part = snippet[:body_start].strip()
        code_part = snippet[body_start:].strip()
        if code_part.endswith(f"// @alex:end {cid}"):
            code_part = code_part[: code_part.rfind(f"// @alex:end {cid}")].strip()
        out[cid] = {
            "full_snippet": snippet,
            "spec_comment_block": spec_part,
            "code_body": code_part,
            "spec_hash": block.get("spec_hash") or "",
            "source_kind": "monolith_import",
        }
    return out
