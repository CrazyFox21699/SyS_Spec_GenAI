"""Assemble traceability.yaml from extracted artifacts."""

from __future__ import annotations

from typing import Any


def build_traceability(
    signals: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    condition_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for t in transitions:
        tid = t.get("id", "TR_???")
        raw = str(t.get("raw_condition", ""))
        sig_names: list[str] = []
        for s in signals:
            n = s.get("name", "")
            if n and n in raw:
                sig_names.append(n)
        rows.append(
            {
                "transition_id": tid,
                "signals_mentioned": sorted(set(sig_names)),
                "raw_condition": raw,
                "from_state": t.get("from_state"),
                "to_state": t.get("to_state"),
                "outputs": t.get("outputs", []),
                "source_evidence": [t.get("source", {})],
                "confidence": t.get("confidence", "low"),
                "review_required": True,
            }
        )
    for ce in condition_entries:
        rows.append(ce)
    return rows


def traceability_for_candidate(
    cand_id: str,
    transition_id: str | None,
    signals: list[str],
    conditions: list[str],
    states: dict[str, str | None],
    outputs: list[str],
    evidence: list[dict[str, Any]],
    confidence: str,
) -> dict[str, Any]:
    return {
        "test_candidate_id": cand_id,
        "transition_id": transition_id,
        "signals": signals,
        "conditions": conditions,
        "states": states,
        "outputs": outputs,
        "source_evidence": evidence,
        "confidence": confidence,
        "review_required": True,
    }
