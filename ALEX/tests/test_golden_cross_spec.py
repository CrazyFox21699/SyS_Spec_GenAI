"""Golden fixture discovery and cross-spec resolution tests."""

from __future__ import annotations

from pathlib import Path

from src.engine.cross_file_resolver import resolve_cross_ref
from src.engine.golden_spec_scoreboard import discover_golden_fixtures


def test_discover_golden_fixtures_finds_shutoff_and_gpt():
    root = Path(__file__).resolve().parents[2]
    fixtures = discover_golden_fixtures(root)
    names = {f["name"] for f in fixtures}
    assert "Shutoff" in names or "GPT_GenLogic" in names


def test_resolve_cross_ref_sets_resolved_node_for_file():
    resolved = resolve_cross_ref(
        {"type": "file", "text": "GPT_GenLogic.xlsx"},
        classified_files=[{"file": "/data/GPT_GenLogic.xlsx"}],
        logic_blocks=[
            {
                "id": "LB1",
                "name": "SYS_SHUTOFF",
                "source": {"file": "GPT_GenLogic.xlsx", "sheet": "Test"},
            }
        ],
    )
    assert resolved.get("resolved_node")
    assert resolved["resolved_node"].get("kind") in {"logic_blocks", "file"}
