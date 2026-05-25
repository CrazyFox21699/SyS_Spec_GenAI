"""Derive MCDC-oriented coverage intent (satisfy vs violate) per test candidate."""

from __future__ import annotations

from typing import Any


def path_coverage_intent(candidate: dict[str, Any]) -> str:
    """Return ``satisfy`` or ``violate`` for assigning constraint values to a path.

    MCDC negation paths and guard-false branches should use out-of-range /
    false-side values; default paths use in-range / true-side values.
    """
    trace = candidate.get("traceability") or {}
    path = str(trace.get("path_id") or trace.get("logic_branch") or "").lower()
    label = str(trace.get("path_label") or trace.get("label") or "").lower()
    mcdc = str(trace.get("mcdc") or "").lower()
    if "_mcdc_neg" in path or "guard_false" in path or "guard_false" in label:
        return "violate"
    if mcdc in ("negate_primary", "negated"):
        return "violate"
    if trace.get("negated") is True:
        return "violate"
    return "satisfy"
