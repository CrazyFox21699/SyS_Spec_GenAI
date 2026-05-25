"""Promote state_machines lifecycle grammar into transition records."""

from __future__ import annotations

from typing import Any


def lifecycle_to_transitions(state_machines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sm in state_machines or []:
        state_name = str(sm.get("state_name") or sm.get("name") or "").strip()
        if not state_name:
            continue
        src = sm.get("source") or {}
        for kind, key in (("start", "start_condition"), ("finish", "finish_condition")):
            cond = sm.get(key)
            if not isinstance(cond, dict):
                continue
            raw = str(cond.get("raw") or cond.get("from_state") or "")
            out.append(
                {
                    "from_state": str(cond.get("from_state") or state_name),
                    "to_state": str(cond.get("to_state") or state_name),
                    "event": kind,
                    "raw_condition": raw or str(cond),
                    "derivation": "lifecycle_grammar",
                    "state_machine": state_name,
                    "source": src,
                    "review_required": True,
                    "confidence": "medium",
                }
            )
    return out
