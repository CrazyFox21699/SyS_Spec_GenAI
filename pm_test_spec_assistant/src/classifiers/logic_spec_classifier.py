"""Detect whether a document is a formal logic specification (structural heuristics)."""

from __future__ import annotations

import re
from typing import Any

_EDGE_RE = re.compile(r"(OFF\s*→\s*ON|ON\s*→\s*OFF|0\s*→\s*1|1\s*→\s*0|==\s*0\s*→\s*==\s*1)", re.I)
_LIFECYCLE_RE = re.compile(
    r"\b(get\s+started|finish|initial\s+value)\b",
    re.I,
)
_LOGIC_OPS_RE = re.compile(r"\b(AND|OR)\b")
_CONSTANT_SYMBOL_RE = re.compile(r"\bT\d+\b|\bV\d+\b|\bN\d+\b")
_TRANSITION_RE = re.compile(r"\b(previous|next)\s+state\b", re.I)

_SIGNAL_WEIGHTS: list[tuple[str, float, re.Pattern[str] | None]] = [
    ("logic_ops_in_tables", 0.25, _LOGIC_OPS_RE),
    ("edge_notation", 0.20, _EDGE_RE),
    ("lifecycle_keywords", 0.15, _LIFECYCLE_RE),
    ("initial_value", 0.10, re.compile(r"\binitial\s+value\b", re.I)),
    ("constant_symbols", 0.10, _CONSTANT_SYMBOL_RE),
    ("state_transitions", 0.10, _TRANSITION_RE),
    ("control_condition_headers", 0.10, re.compile(r"\bcontrol\b.*\bcondition\b", re.I)),
]


def classify_logic_spec(
    text: str,
    *,
    table_samples: list[list[list[str]]] | None = None,
    threshold: float = 0.35,
) -> dict[str, Any]:
    """
    Score a document for logic-spec characteristics (section 10 of formal model).
    Returns score, matched signals, and is_logic_spec boolean.
    """
    corpus_parts = [text or ""]
    for grid in table_samples or []:
        for row in grid[:40]:
            corpus_parts.append(" | ".join(str(c) for c in row if c))
    corpus = "\n".join(corpus_parts)

    matched: list[str] = []
    score = 0.0
    for name, weight, pattern in _SIGNAL_WEIGHTS:
        if pattern and pattern.search(corpus):
            matched.append(name)
            score += weight

    if table_samples:
        for grid in table_samples:
            if not grid:
                continue
            header = " ".join(str(c).lower() for c in grid[0])
            if "control" in header and "condition" in header:
                if "control_condition_headers" not in matched:
                    matched.append("control_condition_headers")
                    score += 0.10
                break

    score = min(score, 1.0)
    return {
        "is_logic_spec": score >= threshold,
        "score": score,
        "signals": matched,
        "threshold": threshold,
    }
