"""Detect Excel sequential/priority decision logic vs boolean OR."""

from __future__ import annotations

import re
from typing import Any

PRIORITY_PHRASES = (
    re.compile(r"shall\s+not\s+be\s+judged", re.I),
    re.compile(r"other\s+conditions\s+(?:shall\s+)?not", re.I),
    re.compile(r"first\s+(?:condition|match|row)\s+(?:wins|applies)", re.I),
    re.compile(r"exclusive\s+(?:selection|choice)", re.I),
    re.compile(r"if\s+condition\s+[a-z]\s+is\s+met", re.I),
)


def detect_decision_mode(texts: list[str]) -> str:
    """
    Return decision_mode: sequential | boolean.
    Default boolean preserves existing gate-spine OR/AND semantics.
    """
    corpus = "\n".join(str(t or "") for t in texts if t)
    if not corpus.strip():
        return "boolean"
    for pattern in PRIORITY_PHRASES:
        if pattern.search(corpus):
            return "sequential"
    return "boolean"


def annotate_logic_block_decision_mode(block: dict[str, Any], context_texts: list[str]) -> dict[str, Any]:
    """Add optional decision_mode field to a logic block."""
    mode = detect_decision_mode(context_texts)
    if mode != "boolean":
        block["decision_mode"] = mode
    else:
        block.setdefault("decision_mode", "boolean")
    return block
