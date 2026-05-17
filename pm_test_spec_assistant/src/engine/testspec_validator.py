"""Validate customer TestSpec I/O columns (Given/Precondition/Then lines)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.concrete_test_values import _GENERIC_TEXT

_LINE_PREFIXES = ("given:", "precondition:", "then:", "when:")
_DICT_LIKE = re.compile(r"^\s*[\{'\"]")
_HAS_GIVEN_OR_PRE = re.compile(r"(?im)^\s*(given:|precondition:)")
_HAS_THEN = re.compile(r"(?im)^\s*then:")


def _split_lines(block: str) -> list[str]:
    return [ln.strip() for ln in str(block or "").splitlines() if ln.strip()]


def _validate_line(line: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    low = line.lower()
    if _DICT_LIKE.match(line):
        issues.append(
            {
                "code": "dict_like",
                "severity": "error",
                "message": "Python dict or JSON blob is not allowed in I/O columns",
            }
        )
        return issues
    if _GENERIC_TEXT.search(line):
        issues.append(
            {
                "code": "generic_prose",
                "severity": "error",
                "message": "Generic prose is not allowed; use concrete Given:/Then: lines",
            }
        )
    if not any(low.startswith(p) for p in _LINE_PREFIXES):
        issues.append(
            {
                "code": "bad_prefix",
                "severity": "error",
                "message": "Line must start with Given:, Precondition:, Then:, or When:",
            }
        )
        return issues
    if low.startswith("given:"):
        body = line.split(":", 1)[-1].strip()
        if "=" not in body:
            issues.append(
                {
                    "code": "given_format",
                    "severity": "warning",
                    "message": "Given line should use SIG=value form",
                }
            )
    if low.startswith("then:"):
        body = line.split(":", 1)[-1].strip()
        if not body:
            issues.append({"code": "empty_then", "severity": "error", "message": "Then: line is empty"})
        elif "=" not in body and not re.search(r"\b(OFF|ON|PASS|FAIL|TRUE|FALSE)\b", body, re.I):
            issues.append(
                {
                    "code": "then_format",
                    "severity": "warning",
                    "message": "Then line should use SIG=value or explicit state",
                }
            )
    return issues


def validate_workbook_io(
    expected_input: str,
    expected_output: str,
    *,
    require_then: bool = True,
) -> dict[str, Any]:
    """
    Returns {ok, quality_score, issues[], summary}.
    quality_score 0–100 (100 = no issues).
    """
    all_issues: list[dict[str, Any]] = []
    inp_lines = _split_lines(expected_input)
    out_lines = _split_lines(expected_output)

    if not inp_lines and not out_lines:
        all_issues.append(
            {
                "code": "empty_io",
                "severity": "error",
                "message": "Expected input and output are both empty",
                "column": "both",
            }
        )

    if inp_lines and not _HAS_GIVEN_OR_PRE.search(expected_input):
        all_issues.append(
            {
                "code": "missing_given",
                "severity": "warning",
                "message": "Expected input has lines but no Given: or Precondition:",
                "column": "expected_input",
            }
        )

    if require_then and out_lines and not _HAS_THEN.search(expected_output):
        all_issues.append(
            {
                "code": "missing_then",
                "severity": "error",
                "message": "Expected output must include Then: lines",
                "column": "expected_output",
            }
        )

    for line in inp_lines:
        for issue in _validate_line(line):
            all_issues.append({**issue, "column": "expected_input", "line": line[:120]})

    for line in out_lines:
        for issue in _validate_line(line):
            all_issues.append({**issue, "column": "expected_output", "line": line[:120]})

    errors = sum(1 for i in all_issues if i.get("severity") == "error")
    warnings = sum(1 for i in all_issues if i.get("severity") == "warning")
    penalty = errors * 25 + warnings * 8
    score = max(0, min(100, 100 - penalty))
    ok = errors == 0 and (bool(out_lines) or not require_then)

    return {
        "ok": ok,
        "quality_score": score,
        "issues": all_issues,
        "summary": f"{errors} error(s), {warnings} warning(s)" if all_issues else "ok",
    }
