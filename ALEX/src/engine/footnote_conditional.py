"""Parse conditional footnote bodies (e.g. Lost = 2026 when OK_SHUTOFF = 1)."""

from __future__ import annotations

import re
from typing import Any

_WHEN_RE = re.compile(
    r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>[-+]?\d+(?:\.\d+)?)\s+when\s+"
    r"(?P<cond>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<cval>[-+]?\d+(?:\.\d+)?)",
    re.I,
)
_OTHERWISE_RE = re.compile(
    r"otherwise,?\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>[-+]?\d+(?:\.\d+)?)",
    re.I,
)
_FOOTNOTE_LINE_RE = re.compile(r"^\(\*(\d+)\)\s+(.+)$", re.I)


def parse_conditional_footnote(body: str) -> dict[str, Any] | None:
    text = str(body or "").strip()
    if not text:
        return None
    m = _WHEN_RE.search(text)
    if not m:
        return None
    var = m.group("var").strip()
    otherwise_val = None
    om = _OTHERWISE_RE.search(text)
    if om and om.group("var").strip().lower() == var.lower():
        otherwise_val = om.group("val").strip()
    return {
        "variable": var,
        "when_true": {
            "condition_signal": m.group("cond").strip(),
            "condition_value": m.group("cval").strip(),
            "variable_value": m.group("val").strip(),
        },
        "otherwise_value": otherwise_val,
        "raw": text,
    }


def given_lines_for_footnote_rule(rule: dict[str, Any], *, branch: str = "when") -> list[str]:
    """Materialize Given/Precondition lines from a parsed conditional footnote rule."""
    if not rule:
        return []
    var = rule.get("variable", "Lost")
    if branch == "when":
        wt = rule.get("when_true") or {}
        cond_sig = wt.get("condition_signal", "")
        cond_val = wt.get("condition_value", "1")
        var_val = wt.get("variable_value", "")
        lines = []
        if cond_sig:
            lines.append(f"Given: {cond_sig}={cond_val}")
        if var and var_val:
            lines.append(f"Given: {var}={var_val}")
        return lines
    ov = rule.get("otherwise_value")
    if ov is not None and var:
        return [f"Given: {var}={ov}"]
    return []


def extract_footnote_lines_from_paragraphs(paragraphs: list[str]) -> dict[str, str]:
    """Collect (*n) footnote bodies from paragraph list."""
    out: dict[str, str] = {}
    for raw in paragraphs:
        line = str(raw or "").strip()
        m = _FOOTNOTE_LINE_RE.match(line)
        if m:
            out[f"(*{m.group(1)})"] = m.group(2).strip()
    return out
