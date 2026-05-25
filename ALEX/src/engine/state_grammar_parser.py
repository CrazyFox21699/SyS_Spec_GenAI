"""Detect state-machine grammar blocks (Initial value / Get Started / Finish)."""

from __future__ import annotations

import re
from typing import Any

from src.engine.logic_keywords import (
    _INITIAL_VALUE_RE,
    _STATE_HEADING_RE,
    normalize_lifecycle_label,
    parse_edge_event,
)

_ASSIGN_RE = re.compile(
    r"^\s*(?P<state>[A-Za-z][A-Za-z0-9_]*)\s*:=\s*(?P<value>.+?)\s*$",
    re.I,
)


def _blank_state_machine(state: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": state,
        "initial_value": None,
        "start_condition": None,
        "finish_condition": None,
        "start_expression": "",
        "finish_expression": "",
        "source": dict(source),
    }


def parse_state_blocks_from_paragraphs(
    lines: list[str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse narrative state blocks from paragraph lines."""
    machines: list[dict[str, Any]] = []
    current_state: str | None = None
    current: dict[str, Any] | None = None

    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue

        m_state = _STATE_HEADING_RE.match(text)
        if m_state and text.lower().startswith("state "):
            if current:
                machines.append(current)
            current_state = m_state.group("state").strip().upper().replace(" ", "_")
            current = _blank_state_machine(current_state, source)
            continue

        if current is None:
            continue

        m_init = _INITIAL_VALUE_RE.match(text)
        if m_init:
            current["initial_value"] = m_init.group("value").strip()
            continue

        kind = normalize_lifecycle_label(text.split(":")[0] if ":" in text else text)
        if kind == "start":
            expr = text.split(":", 1)[-1].strip()
            current["start_expression"] = expr
            current["start_condition"] = parse_edge_event(expr) or {"raw": expr}
            continue
        if kind == "finish":
            expr = text.split(":", 1)[-1].strip()
            current["finish_expression"] = expr
            current["finish_condition"] = parse_edge_event(expr) or {"raw": expr}
            continue

        m_assign = _ASSIGN_RE.match(text)
        if m_assign and kind:
            target = m_assign.group("state")
            value = m_assign.group("value")
            if kind == "start":
                current["start_expression"] = text
                current["start_condition"] = {"assign": target, "value": value, "raw": text}
            elif kind == "finish":
                current["finish_expression"] = text
                current["finish_condition"] = {"assign": target, "value": value, "raw": text}

    if current:
        machines.append(current)
    return [m for m in machines if any([m.get("initial_value"), m.get("start_expression"), m.get("finish_expression")])]


def parse_state_blocks_from_tables(
    table_payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Detect lifecycle rows in Control|Condition tables.
    table_payload: {grid, source, control_name?}
    """
    machines: list[dict[str, Any]] = []
    for payload in table_payloads:
        grid = payload.get("grid") or []
        if len(grid) < 2:
            continue
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        control_name = str(payload.get("control_name") or "STATE").strip().upper()
        header = [c.lower() for c in grid[0]]
        ctrl_idx = next((i for i, h in enumerate(header) if "control" in h or h == "item"), 0)
        cond_idx = next((i for i, h in enumerate(header) if "condition" in h or h == "cond"), 1)

        current = _blank_state_machine(control_name, source)
        found = False
        pending_initial = False
        for row in grid[1:]:
            if ctrl_idx >= len(row):
                continue
            control = str(row[ctrl_idx] or "").strip()
            condition = str(row[cond_idx] if cond_idx < len(row) else "").strip()

            if control and control.lower() not in {"", "control"} and not normalize_lifecycle_label(control):
                if normalize_lifecycle_label(condition) == "initial_value":
                    pending_initial = True
                    control_name = control.upper()
                    current = _blank_state_machine(control_name, source)
                    found = True
                    continue
                control_name = control.upper()
                if found:
                    machines.append(current)
                current = _blank_state_machine(control_name, source)
                found = False
                pending_initial = False

            kind = normalize_lifecycle_label(control) or normalize_lifecycle_label(condition)
            if pending_initial and condition:
                current["initial_value"] = condition
                pending_initial = False
                found = True
                continue
            if not kind:
                continue
            found = True
            if kind == "initial_value":
                current["initial_value"] = condition or control
            elif kind == "start":
                expr = condition or control
                current["start_expression"] = expr
                current["start_condition"] = parse_edge_event(expr) or {"raw": expr}
            elif kind == "finish":
                expr = condition or control
                current["finish_expression"] = expr
                current["finish_condition"] = parse_edge_event(expr) or {"raw": expr}

        if found:
            machines.append(current)

    return [m for m in machines if any([m.get("initial_value"), m.get("start_expression"), m.get("finish_expression")])]
