"""Semi-auto link transitions / diagram edges to logic blocks."""

from __future__ import annotations

from typing import Any


def infer_transition_logic_links(
    transitions: list[dict[str, Any]],
    logic_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tr in transitions or []:
        row = dict(tr)
        if row.get("logic_id") or row.get("inferred_logic_id"):
            out.append(row)
            continue
        hay = " ".join(
            str(row.get(k) or "")
            for k in ("raw_condition", "event", "from_state", "to_state", "edge_label")
        )
        for lb in logic_blocks or []:
            lid = str(lb.get("id") or lb.get("name") or "")
            labels = [
                str(lb.get("name") or ""),
                str(lb.get("outcome_label") or ""),
                str(lb.get("control_name") or ""),
            ]
            if any(label and label in hay for label in labels if label):
                row["inferred_logic_id"] = lid
                break
        out.append(row)
    return out
