"""Suggest improved test spec descriptions from extracted context."""

from __future__ import annotations

from typing import Any


def suggest_description_improvement(candidate: dict[str, Any]) -> dict[str, Any] | None:
    current = str(candidate.get("use_case_description", "")).strip()
    op = candidate.get("operation") or {}
    given = op.get("given") or []
    when = op.get("when") or []
    exp = candidate.get("expectation") or []

    signals_mentioned: list[str] = []
    for g in given:
        if isinstance(g, dict) and g.get("signal"):
            signals_mentioned.append(f"{g['signal']}={g.get('value')}")

    timing_bits = [str(w) for w in when if w]
    exp_bits = [str(e.get("description", e)) if isinstance(e, dict) else str(e) for e in exp]

    missing: list[str] = []
    if len(current) < 40:
        missing.append("Description is too short for customer-facing spec")
    if not any("timing" in str(g).lower() or "ms" in str(g).lower() for g in given + when):
        if timing_bits:
            missing.append("Timing condition not stated in description")
    if not signals_mentioned:
        missing.append("No explicit signal values in Given")
    if not exp_bits or all("consistent with" in b for b in exp_bits):
        missing.append("Concrete expected outputs (e.g. Mode_STS=0)")

    if not missing and len(current) > 80:
        return None

    suggested_parts = [current or "Verify power mode behavior"]
    if signals_mentioned:
        suggested_parts.append(f"when {', '.join(signals_mentioned[:5])}")
    if timing_bits:
        suggested_parts.append(f"and {timing_bits[0]}")
    if exp_bits:
        suggested_parts.append(f"then {exp_bits[0][:120]}")

    suggested = ". ".join(suggested_parts)
    if not suggested.endswith("."):
        suggested += "."

    trace = candidate.get("traceability") or {}
    evidence = trace.get("source_evidence") if isinstance(trace, dict) else []
    if not isinstance(evidence, list):
        evidence = [evidence] if evidence else []

    added: list[str] = []
    if signals_mentioned:
        added.append("explicit signal values in Given")
    if timing_bits:
        added.append("timing / stability condition")
    if exp_bits:
        added.append("concrete expected result")
    trace = candidate.get("traceability") or {}
    pre = candidate.get("precondition") or []
    if pre:
        added.append("source/target state context")

    return {
        "current_description": current,
        "suggested_description": suggested,
        "reason": "; ".join(missing) if missing else "Clarify trigger, timing, and expected outputs",
        "missing_information": missing,
        "missing_in_current": missing,
        "added_information": added,
        "source_evidence": evidence,
        "confidence": candidate.get("confidence", "medium"),
        "review_required": True,
        "source": "deterministic_improver",
    }
