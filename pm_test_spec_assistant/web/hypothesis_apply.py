"""Apply accepted reasoning hypothesis claims to engineer definitions and TCs."""

from __future__ import annotations

from typing import Any

from src.engine.definition_apply import apply_engineer_definitions_to_candidates


def accept_hypothesis_claims(
    bundle: dict[str, Any],
    logic_id: str,
    hypothesis: dict[str, Any],
    *,
    claim_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Merge selected hypothesis claims into engineer_definitions and refresh TC Given."""
    claims = hypothesis.get("claims") or []
    if not isinstance(claims, list):
        return {"ok": False, "error": "Invalid claims list.", "applied_terms": [], "definitions_applied": 0}

    selected = set(int(i) for i in (claim_indices or []))
    if not selected:
        selected = set(range(len(claims)))

    ai = bundle.setdefault("ai_assists", {})
    engineer_defs = ai.setdefault("engineer_definitions", {})
    applied_terms: list[str] = []

    for idx, claim in enumerate(claims):
        if idx not in selected or not isinstance(claim, dict):
            continue
        term = str(claim.get("term") or claim.get("signal") or "").strip()
        definition = str(claim.get("definition") or claim.get("value") or claim.get("claim") or "").strip()
        if not term or not definition:
            continue
        engineer_defs[term] = {
            "definition": definition,
            "logic_id": logic_id,
            "source": "reasoning_hypothesis",
            "citations": claim.get("citations") or [],
            "confidence": claim.get("confidence") or "medium",
        }
        applied_terms.append(term)

    defs_applied = apply_engineer_definitions_to_candidates(bundle, logic_id) if applied_terms else 0
    return {
        "ok": True,
        "applied_terms": applied_terms,
        "definitions_applied": defs_applied,
    }
