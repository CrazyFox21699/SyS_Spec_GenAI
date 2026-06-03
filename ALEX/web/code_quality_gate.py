"""Deterministic quality gate for generated GTest code."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from web.project_code_config import parse_forbidden_patterns

_GIVEN_RE = re.compile(r"^Given:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=", re.I | re.M)
_WHEN_TIME_RE = re.compile(r"(?:When:)?\s*(?:elapsed_time|time)\s*(?:>=|>|=)\s*(\d+)\s*ms", re.I)
_THEN_SIG_RE = re.compile(r"^Then:\s*(?P<sig>[A-Za-z_][A-Za-z0-9_.]*)\s*=", re.I | re.M)
_TEST_SIG_RE = re.compile(r"\bTEST(?:_F)?\s*\(\s*[^,]+,\s*([^)]+)\s*\)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    severity: str,
    message: str,
    candidate_id: str,
) -> None:
    checks.append(
        {
            "testcase_id": candidate_id,
            "check_name": name,
            "severity": severity,
            "message": message,
            "generated_at": _now_iso(),
        }
    )


def _signals_from_io(text: str) -> dict[str, set[str]]:
    given: set[str] = set()
    then: set[str] = set()
    has_timing = False
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        gm = _GIVEN_RE.match(s)
        if gm:
            given.add(gm.group("sig"))
        tm = _THEN_SIG_RE.match(s)
        if tm:
            then.add(tm.group("sig"))
        if _WHEN_TIME_RE.search(s):
            has_timing = True
    return {"given": given, "then": then, "has_timing": has_timing}


def _code_references_signal(code: str, sig: str) -> bool:
    if not sig:
        return False
    esc = re.escape(sig)
    patterns = [
        rf"\b{esc}\b",
        rf"\.{esc}\b",
        rf"SetSignal\s*\([^)]*{esc}",
        rf"EXPECT_\w+\s*\([^)]*{esc}",
    ]
    return any(re.search(p, code, re.I) for p in patterns)


def _code_has_timing_wait(code: str) -> bool:
    return bool(
        re.search(r"\b(RunForMs|WaitMs|sleep|advance_time|elapsed)\b", code, re.I)
        or re.search(r"\b\d+\s*ms\b", code, re.I)
    )


_FALLBACK_SCAFFOLD_RE = re.compile(r'GTEST_SKIP\s*\(\s*\)\s*<<\s*"NEEDS_REVIEW:', re.I)
_TODO_REVIEW_RE = re.compile(r'\bTODO_REVIEW\b', re.I)


def is_fallback_scaffold(code: str) -> bool:
    """True when code is a GTEST_SKIP fallback scaffold, not real generated code."""
    return bool(_FALLBACK_SCAFFOLD_RE.search(str(code or "")))


def is_partial_generated_code(code: str) -> bool:
    """True when Copilot returned real code with TODO_REVIEW markers for unclear parts."""
    body = str(code or "")
    return (
        bool(_TODO_REVIEW_RE.search(body))
        and bool(re.search(r"\bTEST(?:_F)?\s*\(", body))
        and not is_fallback_scaffold(body)
    )


def run_quality_gate(
    code: str,
    *,
    candidate_id: str = "",
    structured_io: dict[str, Any] | None = None,
    code_rules_md: str = "",
    api_catalog_yaml: str = "",
    sample_snippet: str = "",
    expected_input: str = "",
    expected_output: str = "",
) -> dict[str, Any]:
    """Return summary PASS | WARNING | FAIL and per-check rows."""
    checks: list[dict[str, Any]] = []
    body = str(code or "").strip()
    cid = str(candidate_id or "").strip()

    if is_fallback_scaffold(body):
        _check(
            checks,
            name="fallback_scaffold",
            severity="WARNING",
            message="Fallback scaffold — replace with project-specific code before approval",
            candidate_id=cid,
        )
        return _finalize(checks)

    if not body:
        _check(checks, name="empty_code", severity="FAIL", message="Code is empty", candidate_id=cid)
        return _finalize(checks)

    if "```" in body:
        _check(checks, name="markdown_fence", severity="FAIL", message="Contains markdown fence", candidate_id=cid)

    if not re.search(r"\bTEST(?:_F)?\s*\(", body):
        _check(checks, name="missing_TEST", severity="FAIL", message="Missing TEST or TEST_F", candidate_id=cid)

    has_expect = bool(re.search(r"\bEXPECT_(EQ|NE|TRUE|FALSE|THAT)\b", body))
    has_assert = bool(re.search(r"\bASSERT_(EQ|NE|TRUE|FALSE|THAT)\b", body))
    if not has_expect and not has_assert:
        _check(checks, name="missing_EXPECT", severity="WARNING", message="Missing EXPECT or ASSERT", candidate_id=cid)

    if cid and cid not in body:
        _check(
            checks,
            name="missing_testcase_id",
            severity="WARNING",
            message="testcase_id not found in comments or code",
            candidate_id=cid,
        )

    if re.search(r"\bTODO_REVIEW\b", body, re.I):
        _check(checks, name="todo_review", severity="WARNING",
               message="Contains TODO_REVIEW — partial generated code; review these locations",
               candidate_id=cid)
    elif re.search(r"\bTODO\b", body, re.I):
        _check(checks, name="todo", severity="WARNING", message="Contains TODO", candidate_id=cid)

    for pat in parse_forbidden_patterns(code_rules_md):
        if pat == "TODO" and re.search(r"\bTODO\b", body, re.I):
            continue
        if pat in body:
            _check(
                checks,
                name="forbidden_pattern",
                severity="WARNING",
                message=f"Forbidden pattern from code_rules: {pat}",
                candidate_id=cid,
            )

    io_text = f"{expected_input}\n{expected_output}"
    if structured_io:
        io_text = "\n".join(
            (structured_io.get("given_lines") or [])
            + (structured_io.get("when_lines") or [])
            + (structured_io.get("then_lines") or [])
        )
    io = _signals_from_io(io_text)

    for sig in sorted(io["given"]):
        if not _code_references_signal(body, sig):
            _check(
                checks,
                name="missing_input_setup",
                severity="WARNING",
                message=f"Input signal not referenced in code: {sig}",
                candidate_id=cid,
            )

    for sig in sorted(io["then"]):
        if not _code_references_signal(body, sig):
            _check(
                checks,
                name="missing_assertion",
                severity="WARNING",
                message=f"Expected output not asserted for: {sig}",
                candidate_id=cid,
            )

    if io.get("has_timing") and not _code_has_timing_wait(body):
        _check(
            checks,
            name="timing_issue",
            severity="WARNING",
            message="Spec has timing but code has no wait/advance",
            candidate_id=cid,
        )

    from web.config_yaml_parsers import api_matches_catalog, parse_api_catalog_full

    catalog_full = parse_api_catalog_full(api_catalog_yaml)
    if catalog_full.get("apis") or catalog_full.get("wildcards") or sample_snippet.strip():
        from web.code_style_samples import _api_calls_from_cpp

        builtins = {
            "TEST",
            "TEST_F",
            "EXPECT_EQ",
            "EXPECT_NE",
            "EXPECT_TRUE",
            "EXPECT_FALSE",
            "if",
            "for",
            "while",
            "return",
        }
        sample_apis = _api_calls_from_cpp(sample_snippet) - builtins
        code_apis = _api_calls_from_cpp(body) - builtins
        unknown = sorted(
            a
            for a in code_apis
            if a not in sample_apis and not api_matches_catalog(a, catalog_full)
        )
        if unknown:
            _check(
                checks,
                name="unknown_api",
                severity="WARNING",
                message=f"API not in catalog or sample: {', '.join(unknown[:6])}",
                candidate_id=cid,
            )

    if not any(c["severity"] == "FAIL" for c in checks):
        _check(checks, name="basic_structure", severity="PASS", message="Basic structure OK", candidate_id=cid)

    return _finalize(checks)


def _finalize(checks: list[dict[str, Any]]) -> dict[str, Any]:
    if any(c["severity"] == "FAIL" for c in checks):
        summary = "FAIL"
    elif any(c["severity"] == "WARNING" for c in checks):
        summary = "WARNING"
    else:
        summary = "PASS"
    return {
        "summary": summary,
        "quality_summary": summary,
        "checks": checks,
        "warning_count": sum(1 for c in checks if c["severity"] == "WARNING"),
        "fail_count": sum(1 for c in checks if c["severity"] == "FAIL"),
    }


def quality_to_code_status(quality_summary: str) -> str:
    q = str(quality_summary or "").upper()
    if q == "PASS":
        return "SAVED"
    if q == "WARNING":
        return "NEEDS_REVIEW"
    return "ERROR"
