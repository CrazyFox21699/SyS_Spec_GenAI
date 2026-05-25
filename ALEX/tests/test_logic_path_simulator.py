from __future__ import annotations

from src.engine.condition_tree_builder import parse_condition_tree
from src.engine.logic_path_simulator import collect_simulation_signals, simulate_logic_path


def test_simulate_active_boolean_path() -> None:
    raw = "PWR_REQ_VALID AND VEHICLE_SAFE AND NOT NOK_SHUTOFF"
    tree = parse_condition_tree(raw)
    signals = collect_simulation_signals(tree)
    names = {row["signal"] for row in signals}
    assert "PWR_REQ_VALID" in names
    assert "NOK_SHUTOFF" in names

    result = simulate_logic_path(
        tree,
        {"PWR_REQ_VALID": 1, "VEHICLE_SAFE": 1, "NOK_SHUTOFF": 0},
    )
    assert result["status"] == "active"
    assert result["result"] is True
    assert result["active_node_ids"]


def test_simulate_inactive_when_flag_missing() -> None:
    tree = parse_condition_tree("PWR_REQ_VALID AND VEHICLE_SAFE")
    result = simulate_logic_path(tree, {"PWR_REQ_VALID": 1, "VEHICLE_SAFE": 0})
    assert result["status"] == "inactive"
    assert result["result"] is False
