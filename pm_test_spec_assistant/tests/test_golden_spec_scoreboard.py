from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.golden_spec_scoreboard import (
    build_spec_scoreboard,
    discover_golden_fixtures,
    evaluate_scoreboard,
)
from src.pipeline import run_analyze


def test_build_spec_scoreboard_from_bundle_shape() -> None:
    board = build_spec_scoreboard(
        {
            "logic_review_items": [
                {"parse_status": "ok"},
                {"parse_status": "partial"},
            ],
            "issues": [{"severity": "error"}],
            "spec_understanding": {"overall": {"understanding_percent": 40, "status": "partial"}},
            "evidence_registry": {"total": 25},
        },
        fixture_name="GPT_GenLogic",
    )
    assert board["controls_total"] == 2
    assert board["controls_ok"] == 1
    assert board["controls_partial"] == 1
    assert board["controls_ok_percent"] == 50.0
    assert board["evidence_total"] == 25


def test_evaluate_scoreboard_passes_minimal_fixture() -> None:
    board = build_spec_scoreboard({"logic_review_items": [{"parse_status": "ok"}], "issues": []}, fixture_name="Shutoff")
    result = evaluate_scoreboard(board, fixture_name="Shutoff")
    assert result["passed"] is True


def test_gpt_genlogic_golden_scoreboard_when_sample_present() -> None:
    root = Path(__file__).resolve().parents[2]
    fixtures = discover_golden_fixtures(root)
    gpt = next((f for f in fixtures if f["name"] == "GPT_GenLogic"), None)
    if not gpt:
        pytest.skip("GPT_GenLogic sample not available")

    input_path = Path(gpt["path"])
    out = root / "pm_test_spec_assistant" / "output" / "_pytest_golden_gpt"
    cfg = Path(__file__).resolve().parents[1] / "config.yaml"
    bundle = run_analyze(input_path, out, cfg, force=True)
    board = build_spec_scoreboard(bundle, fixture_name="GPT_GenLogic")
    result = evaluate_scoreboard(board, fixture_name="GPT_GenLogic")
    assert board["controls_total"] >= 1
    assert board["evidence_total"] >= 10
    assert "checks" in result
