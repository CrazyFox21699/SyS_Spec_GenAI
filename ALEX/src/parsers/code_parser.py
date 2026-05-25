"""Source / GTest code hints."""

from __future__ import annotations

import re
from pathlib import Path


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


def extract_code_reference(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "file": str(path),
        "length_chars": len(text),
        "hints": scan_code_hints(path),
        "note": "v0.1 records style hints only; no codegen.",
    }
