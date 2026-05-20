"""Validation guardrails for AI reasoning hypotheses."""

from __future__ import annotations

from typing import Any


def _has_citation(row: dict[str, Any]) -> bool:
    return bool(
        row.get("candidate_id")
        or row.get("diagram_asset")
        or (row.get("file") and (row.get("row") is not None or row.get("paragraph") is not None))
    )


def validate_reasoning_hypothesis(payload: dict[str, Any], *, logic_id: str = "") -> dict[str, Any]:
    """
    Lightweight schema/guardrail validation without adding a jsonschema dependency.

    Fail closed: executable claims and testcase patch actions require citations.
    Unsupported ideas should be represented as open_questions instead.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["Hypothesis must be a JSON object."], "warnings": []}

    hyp_logic = str(payload.get("logic_id") or "").strip()
    if logic_id and hyp_logic and hyp_logic != logic_id:
        errors.append(f"Hypothesis logic_id `{hyp_logic}` does not match `{logic_id}`.")
    if not hyp_logic:
        errors.append("Missing logic_id.")
    if payload.get("review_required") is not True:
        errors.append("review_required must be true for AI hypotheses.")

    for idx, claim in enumerate(payload.get("claims") or []):
        if not isinstance(claim, dict):
            errors.append(f"claims[{idx}] must be an object.")
            continue
        citations = claim.get("citations") or []
        if not citations or not any(isinstance(c, dict) and _has_citation(c) for c in citations):
            errors.append(f"claims[{idx}] is missing evidence citations.")

    allowed_actions = {"update_existing", "add_new", "retire", "needs_review"}
    for idx, patch in enumerate(payload.get("testcase_patch_plan") or []):
        if not isinstance(patch, dict):
            errors.append(f"testcase_patch_plan[{idx}] must be an object.")
            continue
        action = patch.get("action")
        if action not in allowed_actions:
            errors.append(f"testcase_patch_plan[{idx}] has unsupported action `{action}`.")
        citations = patch.get("citations") or []
        if not citations or not any(isinstance(c, dict) and _has_citation(c) for c in citations):
            errors.append(f"testcase_patch_plan[{idx}] is missing evidence citations.")
        if action in {"update_existing", "retire"} and not patch.get("candidate_id"):
            errors.append(f"testcase_patch_plan[{idx}] action `{action}` requires candidate_id.")

    if not payload.get("claims") and not payload.get("open_questions") and not payload.get("testcase_patch_plan"):
        warnings.append("Hypothesis contains no claims, open questions, or testcase patch plan.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def open_question_for_unsupported_claim(claim: str, *, reason: str = "Missing citation") -> dict[str, Any]:
    return {
        "question": f"Can you provide evidence for: {claim}",
        "reason": reason,
        "citations": [],
    }
