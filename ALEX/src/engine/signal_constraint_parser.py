"""Parse deterministic signal constraints from engineer notes (no AI)."""

from __future__ import annotations

import re
from typing import Any

_SIG = r"[A-Z][A-Z0-9_]*"
_NUM = r"[-+]?\d+(?:\.\d+)?"

_EQ_RE = re.compile(rf"^({_SIG})\s*=\s*(.+)$")
_RANGE_WITH_SIG_RE = re.compile(
    rf"^({_SIG})\s*(?:>=\s*({_NUM})\s*[,;\s]+(?:and\s+)?<\s*({_NUM}))",
    re.I,
)
_RANGE_GT_RE = re.compile(
    rf"^({_SIG})\s*(?:>\s*({_NUM})\s*[,;\s]+(?:and\s+)?<\s*({_NUM}))",
    re.I,
)
_RANGE_SHORT_RE = re.compile(
    rf"^({_SIG})\s+(?:range\s+)?({_NUM})\s*(?:[-–..]|(?:\s+to\s+))\s*({_NUM})(?:\s*\(.+\))?$",
    re.I,
)
_BARE_RANGE_RE = re.compile(
    rf"^>=\s*({_NUM})\s*[,;\s]+(?:and\s+)?<\s*({_NUM})",
    re.I,
)
_BARE_RANGE_GT_RE = re.compile(
    rf"^>\s*({_NUM})\s*[,;\s]+(?:and\s+)?<\s*({_NUM})",
    re.I,
)
_PLAIN_VALUE_RE = re.compile(r"^([-+]?\d+(?:\.\d+)?(?:\s*\([^)]+\))?|[A-Za-z_][A-Za-z0-9_]*)$")


def normalize_range_definition(lo: str, hi: str) -> str:
    return f"range inclusive {lo.strip()}–{hi.strip()}"


def normalize_exclusive_range_definition(lo: str, hi: str) -> str:
    """Exclusive bounds: > lo and < hi."""
    return f"range exclusive {lo.strip()}–{hi.strip()}"


def parse_structured_constraint(definition: str) -> dict[str, Any] | None:
    """Parse definition body into structured constraint when possible."""
    text = str(definition or "").strip()
    m = re.match(r"range inclusive\s+(\S+)\s*[–-]\s*(\S+)", text, re.I)
    if m:
        return {"kind": "range_inclusive", "lo": m.group(1), "hi": m.group(2)}
    m = re.match(r"range exclusive\s+(\S+)\s*[–-]\s*(\S+)", text, re.I)
    if m:
        return {"kind": "range_exclusive", "lo": m.group(1), "hi": m.group(2)}
    if text.startswith("="):
        return {"kind": "equality", "value": text.lstrip("= ").strip()}
    return None


def _normalize_definition_body(body: str) -> str:
    text = str(body or "").strip()
    if not text:
        return ""
    if re.fullmatch(_NUM, text):
        return f"= {text}"
    if text.startswith("="):
        return text
    if _PLAIN_VALUE_RE.match(text):
        return f"= {text}"
    return text


def parse_signal_constraint_line(line: str, *, focus_term: str = "") -> tuple[str, str] | None:
    """Return (signal, definition_body) when the line is a basic constraint."""
    chunk = str(line or "").strip().strip(",;")
    if not chunk or chunk.startswith("#"):
        return None

    m = _EQ_RE.match(chunk)
    if m:
        return m.group(1).upper(), _normalize_definition_body(m.group(2))

    m = _RANGE_WITH_SIG_RE.match(chunk)
    if m:
        return m.group(1).upper(), normalize_range_definition(m.group(2), m.group(3))

    m = _RANGE_GT_RE.match(chunk)
    if m:
        return m.group(1).upper(), normalize_exclusive_range_definition(m.group(2), m.group(3))

    m = _RANGE_SHORT_RE.match(chunk)
    if m:
        return m.group(1).upper(), normalize_range_definition(m.group(2), m.group(3))

    focus = focus_term.strip().upper()
    if focus:
        m = _BARE_RANGE_RE.match(chunk)
        if m:
            return focus, normalize_range_definition(m.group(1), m.group(2))
        m = _BARE_RANGE_GT_RE.match(chunk)
        if m:
            return focus, normalize_exclusive_range_definition(m.group(1), m.group(2))
        if _PLAIN_VALUE_RE.match(chunk):
            return focus, _normalize_definition_body(chunk)

    return None


def extract_signal_constraints_from_text(
    text: str,
    *,
    focus_term: str = "",
) -> dict[str, str]:
    """Extract basic signal constraints from free-form engineer note text."""
    found: dict[str, str] = {}
    focus = focus_term.strip().upper()
    body = str(text or "").strip()
    if not body:
        return found

    for line in body.splitlines():
        chunk = line.strip()
        if not chunk:
            continue
        parts = [chunk]
        if "," in chunk and re.search(rf",\s*{_SIG}\s*=", chunk):
            parts = [p.strip() for p in re.split(rf",(?=\s*{_SIG}\s*=)", chunk) if p.strip()]
        for part in parts:
            parsed = parse_signal_constraint_line(part, focus_term=focus)
            if parsed:
                found[parsed[0]] = parsed[1]

    if focus and focus not in found:
        parsed = parse_signal_constraint_line(body.splitlines()[0], focus_term=focus)
        if parsed:
            found[parsed[0]] = parsed[1]

    return found


def is_locally_parseable(text: str, *, focus_term: str = "") -> bool:
    """True when note contains at least one basic constraint ALEX can apply without AI."""
    return bool(extract_signal_constraints_from_text(text, focus_term=focus_term))
