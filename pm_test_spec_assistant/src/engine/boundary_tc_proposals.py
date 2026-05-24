"""Propose boundary-violation test cases from engineer definitions."""

from __future__ import annotations

import re
from typing import Any

_BOUNDARY_RE = re.compile(
    r"(?:range|between|from)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:-|to|–)\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)
_SINGLE_BOUND_RE = re.compile(r"(?:>=|<=|>|<|≥|≤)\s*([0-9]+(?:\.[0-9]+)?)")


def _extract_boundaries(definition: str) -> list[tuple[str, float]]:
    text = str(definition or "")
    out: list[tuple[str, float]] = []
    m = _BOUNDARY_RE.search(text)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        out.extend([("below_min", lo - 0.01), ("above_max", hi + 0.01)])
        return out
    for m in _SINGLE_BOUND_RE.finditer(text):
        val = float(m.group(1))
        op = m.group(0).strip()[0]
        if op in (">", "≥"):
            out.append(("below_min", val - 0.01))
        else:
            out.append(("above_max", val + 0.01))
    return out


def propose_boundary_testcases(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    engineer_definitions: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return add_new patch proposals for analog boundary violations."""
    ai = bundle.get("ai_assists") or {}
    defs = engineer_definitions or ai.get("engineer_definitions") or {}
    proposals: list[dict[str, Any]] = []
    existing_ids = {
        str(c.get("id") or c.get("candidate_id") or "")
        for c in bundle.get("test_candidates") or []
        if (c.get("traceability") or {}).get("logic_block") == logic_id
    }

    for term, meta in defs.items():
        if not isinstance(meta, dict):
            continue
        definition = str(meta.get("definition") or "")
        if str(meta.get("logic_id") or logic_id) != logic_id:
            continue
        for intent, value in _extract_boundaries(definition):
            cid = f"{logic_id}_BOUND_{term}_{intent}".replace(" ", "_")[:64]
            if cid in existing_ids:
                continue
            proposals.append(
                {
                    "action": "add_new",
                    "candidate_id": cid,
                    "given": [{"signal": term, "value": str(value), "role": "stimulus"}],
                    "note": f"Boundary probe: {intent} for {term}",
                    "citations": meta.get("citations") or [],
                    "path_coverage_intent": intent,
                }
            )
    return proposals
