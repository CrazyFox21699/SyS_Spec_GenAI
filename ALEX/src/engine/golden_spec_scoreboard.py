"""Golden baseline scoreboard for customer sample specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_spec_scoreboard(bundle: dict[str, Any], *, fixture_name: str = "") -> dict[str, Any]:
    """Summarize parse/readiness metrics from an analyze bundle."""
    items = bundle.get("logic_review_items") or []
    logic_blocks = bundle.get("logic_blocks") or []
    issues = bundle.get("issues") or []
    total = len(items) or len(logic_blocks)
    ok = sum(1 for i in items if str(i.get("parse_status") or "") == "ok")
    partial = sum(1 for i in items if str(i.get("parse_status") or "") == "partial")
    failed = sum(1 for i in items if str(i.get("parse_status") or "") == "failed")
    errors = sum(1 for i in issues if i.get("severity") == "error")
    understanding = (bundle.get("spec_understanding") or {}).get("overall") or {}
    pct_ok = round(100.0 * ok / total, 1) if total else 0.0
    return {
        "fixture": fixture_name,
        "controls_total": total,
        "controls_ok": ok,
        "controls_partial": partial,
        "controls_failed": failed,
        "controls_ok_percent": pct_ok,
        "issues_total": len(issues),
        "issues_error": errors,
        "understanding_percent": understanding.get("understanding_percent"),
        "understanding_status": understanding.get("status"),
        "evidence_total": (bundle.get("evidence_registry") or {}).get("total", 0),
    }


def baseline_thresholds(fixture_name: str) -> dict[str, Any]:
    """Minimum acceptable metrics per golden fixture."""
    name = fixture_name.lower()
    if "gpt_genlogic" in name:
        return {
            "min_controls_total": 1,
            "min_controls_ok_percent": 0.0,
            "min_evidence_total": 10,
            "max_issues_error": 500,
        }
    if "shutoff" in name:
        return {
            "min_controls_total": 1,
            "min_controls_ok_percent": 30.0,
            "min_evidence_total": 0,
            "max_issues_error": 200,
        }
    return {
        "min_controls_total": 1,
        "min_controls_ok_percent": 0.0,
        "min_evidence_total": 0,
        "max_issues_error": 500,
    }


def evaluate_scoreboard(scoreboard: dict[str, Any], *, fixture_name: str = "") -> dict[str, Any]:
    """Check scoreboard against baseline thresholds."""
    fixture = fixture_name or scoreboard.get("fixture") or ""
    thresholds = baseline_thresholds(fixture)
    checks = {
        "controls_total": scoreboard.get("controls_total", 0) >= thresholds["min_controls_total"],
        "controls_ok_percent": scoreboard.get("controls_ok_percent", 0) >= thresholds["min_controls_ok_percent"],
        "evidence_total": scoreboard.get("evidence_total", 0) >= thresholds["min_evidence_total"],
        "issues_error": scoreboard.get("issues_error", 0) <= thresholds["max_issues_error"],
    }
    return {
        "fixture": fixture,
        "scoreboard": scoreboard,
        "thresholds": thresholds,
        "checks": checks,
        "passed": all(checks.values()),
    }


def discover_golden_fixtures(alex_root: Path) -> list[dict[str, str]]:
    """Return available golden input paths under sample_inputs/."""
    samples = alex_root / "sample_inputs"
    fixtures: list[dict[str, str]] = []
    gpt = samples / "GPT_GenLogic.xlsx"
    if not gpt.exists():
        gpt = samples / "input" / "GPT_GenLogic.xlsx"
    if gpt.exists():
        fixtures.append(
            {
                "name": "GPT_GenLogic",
                "path": str(gpt.parent),
                "kind": "dir",
                "file": str(gpt),
            }
        )
    shutoff = samples / "input" / "edited_Shutoff_Condition_Spec.docx"
    if not shutoff.exists():
        shutoff = samples / "edited_Shutoff_Condition_Spec.docx"
    if shutoff.exists():
        fixtures.append(
            {
                "name": "Shutoff",
                "path": str(shutoff.parent),
                "kind": "dir",
                "file": str(shutoff),
            }
        )
    return fixtures
