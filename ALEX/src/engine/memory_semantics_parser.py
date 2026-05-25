"""Multivalued sentinel values and memory / retention semantics."""

from __future__ import annotations

import re
from typing import Any

SENTINEL_VALUES = frozenset(
    {
        "none",
        "invalid",
        "undetermined",
        "processing",
        "not being processed",
        "unknown",
        "n/a",
    }
)

RETENTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("retain_previous", re.compile(r"retain\s+(?:the\s+)?previous\s+(?:confirmed\s+)?value", re.I)),
    ("one_way_latch", re.compile(r"disallowed\s+even\s+once", re.I)),
    ("nvm_store", re.compile(r"non[- ]volatile\s+memory|store\s+to\s+nvm", re.I)),
    ("reset_immune", re.compile(r"not\s+affected\s+by\s+reset|data\s+conversion", re.I)),
]


def classify_value_domain(value: str | None) -> str:
    """Return value domain: boolean | sentinel | enum | literal."""
    if value is None:
        return "literal"
    text = str(value).strip()
    if not text:
        return "literal"
    low = text.lower()
    if low in ("true", "false", "0", "1", "on", "off", "yes", "no"):
        return "boolean"
    if low in SENTINEL_VALUES:
        return "sentinel"
    if re.match(r"^[A-Z][A-Z0-9_]+$", text):
        return "enum"
    return "literal"


def parse_retention_rules(lines: list[str], source: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract non-executable retention / latch rules from paragraph text."""
    rules: list[dict[str, Any]] = []
    for line in lines or []:
        text = str(line or "").strip()
        if not text:
            continue
        for rule_kind, pattern in RETENTION_PATTERNS:
            if pattern.search(text):
                rules.append(
                    {
                        "rule_kind": rule_kind,
                        "raw_text": text,
                        "executable": False,
                        "source": dict(source),
                    }
                )
                break
    return rules


def enrich_condition_definitions(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add value_domain to definitions without normalizing sentinel values."""
    for row in definitions:
        definition = str(row.get("definition") or "")
        m = re.search(r"(==|!=|=)\s*(.+?)\s*$", definition)
        if m:
            row["value_domain"] = classify_value_domain(m.group(2).strip())
        elif row.get("constant_value") is not None:
            row["value_domain"] = classify_value_domain(str(row.get("constant_value")))
    return definitions
