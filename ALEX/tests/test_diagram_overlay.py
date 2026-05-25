from __future__ import annotations

from src.engine.structured_overlay import add_diagram_link, get_overlay


def test_add_diagram_link_stores_accepted_edge() -> None:
    bundle: dict = {"ai_assists": {}}
    link = add_diagram_link(
        bundle,
        "LB1",
        {
            "from_state": "OFF",
            "to_state": "ON",
            "event": "IGN",
            "conditions": ["MODE=1"],
            "edge_key": "edge-1",
        },
    )
    overlay = get_overlay(bundle, "LB1")
    assert link["review_status"] == "accepted"
    assert len(overlay.get("diagram_links") or []) == 1
    assert overlay["diagram_links"][0]["from_state"] == "OFF"


def test_add_diagram_link_replaces_same_edge_key() -> None:
    bundle: dict = {"ai_assists": {}}
    add_diagram_link(bundle, "LB1", {"edge_key": "e1", "from_state": "A", "to_state": "B"})
    add_diagram_link(bundle, "LB1", {"edge_key": "e1", "from_state": "A", "to_state": "C"})
    overlay = get_overlay(bundle, "LB1")
    assert len(overlay["diagram_links"]) == 1
    assert overlay["diagram_links"][0]["to_state"] == "C"
