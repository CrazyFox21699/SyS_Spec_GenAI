from __future__ import annotations

from src.engine.issue_prioritizer import build_overview_dashboard, prioritize_issues


def test_prioritize_issues_orders_errors_first() -> None:
    issues = [
        {"type": "info_note", "severity": "info", "message": "minor"},
        {"type": "logic_block_parse_failed", "severity": "error", "message": "block failed"},
        {"type": "unresolved_condition", "severity": "warning", "message": "missing term"},
    ]
    out = prioritize_issues(issues, limit=5)
    assert out[0]["type"] == "logic_block_parse_failed"
    assert out[0]["priority_rank"] == 1


def test_build_overview_dashboard_counts_logic_groups() -> None:
    bundle = {
        "logic_review_items": [
            {"control_name": "A", "parse_status": "ok"},
            {"control_name": "B", "parse_status": "partial"},
        ],
        "issues": [{"type": "unresolved_condition", "severity": "error", "message": "x", "control": "B"}],
        "spec_understanding": {"overall": {"understanding_percent": 55, "status": "partial"}},
    }
    capability = {
        "logic": {"groups_total": 2, "groups_ok": 1, "groups_partial": 1, "groups_failed": 0},
    }
    overview = build_overview_dashboard(bundle, capability)
    assert overview["logic_groups_ok"] == 1
    assert overview["logic_groups_partial"] == 1
    assert overview["understanding_percent"] == 55
    assert overview["top_blockers"]
