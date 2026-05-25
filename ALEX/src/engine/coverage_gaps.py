"""Generic coverage gap analysis for Copilot Context Pack."""

from __future__ import annotations

from typing import Any

from src.engine.boundary_tc_proposals import propose_boundary_testcases
from src.engine.path_tc_matrix import build_path_tc_matrix
from src.engine.selective_tc_regen import build_path_regen_proposals
from src.engine.verification_patterns import build_verification_matrix
from web.knowledge_validation import compliance_snapshot


def analyze_coverage_gaps(
    bundle: dict[str, Any],
    logic_id: str,
    *,
    engineer_definitions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return structured gaps: missing paths, compliance fails, boundary slots."""
    matrix = build_path_tc_matrix(bundle, logic_id)
    path_regen = build_path_regen_proposals(bundle, logic_id)
    boundary = propose_boundary_testcases(
        bundle, logic_id, engineer_definitions=engineer_definitions
    )
    compliance = compliance_snapshot(bundle, logic_id)

    missing_paths: list[dict[str, Any]] = []
    if matrix.get("ok"):
        for path in matrix.get("paths") or []:
            if path.get("coverage_status") == "missing":
                missing_paths.append(
                    {
                        "path_id": path.get("path_id"),
                        "label": path.get("label"),
                        "signals": path.get("signals") or [],
                        "given_template": path.get("given_template") or [],
                    }
                )

    compliance_fails: list[dict[str, Any]] = []
    for row in compliance:
        if row.get("logic_comply") not in (None, "pass", ""):
            compliance_fails.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "logic_comply": row.get("logic_comply"),
                    "missing_signals": row.get("missing_signals") or [],
                }
            )

    boundary_gaps: list[dict[str, Any]] = []
    for prop in boundary:
        boundary_gaps.append(
            {
                "candidate_id": prop.get("candidate_id"),
                "signal": (prop.get("given") or [{}])[0].get("signal") if prop.get("given") else "",
                "intent": prop.get("path_coverage_intent"),
                "note": prop.get("note"),
            }
        )

    path_regen_patches = (path_regen.get("patches") or []) if path_regen.get("ok") else []
    verification = build_verification_matrix(bundle, logic_id)

    return {
        "logic_id": logic_id,
        "missing_paths": missing_paths,
        "missing_path_count": len(missing_paths),
        "compliance_fails": compliance_fails,
        "compliance_fail_count": len(compliance_fails),
        "boundary_gaps": boundary_gaps,
        "boundary_gap_count": len(boundary_gaps),
        "path_regen_proposals": path_regen_patches,
        "matrix_summary": matrix.get("summary") if matrix.get("ok") else {},
        "verification_matrix": {
            "one_to_many_count": verification.get("one_to_many_count", 0),
            "many_to_one_count": verification.get("many_to_one_count", 0),
            "partial_assert_count": verification.get("partial_assert_count", 0),
            "ambiguous_count": len(verification.get("ambiguous") or []),
        },
    }
