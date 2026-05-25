from __future__ import annotations

from src.engine.use_case_text import compact_use_case_description, sanitize_candidates_use_cases


def test_compact_strips_truncated_raw_expression() -> None:
    cand = {
        "use_case_description": (
            "Verify CND_REQ_GROUP=1 (default_footnote_when; (REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID ()"
        ),
        "traceability": {
            "control_name": "CND_REQ_GROUP",
            "logic_branch": "default_footnote_when",
        },
        "event": "evaluate_CND_REQ_GROUP_default_footnote_when",
    }
    out = compact_use_case_description(cand)
    assert "(*" not in out
    assert "REQ_MAIN_OK" not in out
    assert out == "Verify CND_REQ_GROUP=1 — path default footnote when"


def test_sanitize_bundle_candidates() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_PM_021",
                "use_case_description": "Verify X=1 (branch_1; (A (*1) AND B",
                "traceability": {"control_name": "X", "logic_branch": "branch_1"},
            }
        ]
    }
    fixed = sanitize_candidates_use_cases(bundle)
    desc = fixed["test_candidates"][0]["use_case_description"]
    assert "(*" not in desc
    assert "— path" in desc
