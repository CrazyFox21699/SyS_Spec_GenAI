"""Build Code Context Pack for M365 Copilot GTest generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.engine.path_tc_matrix import _candidate_logic_id
from src.engine.verification_patterns import (
    _given_fingerprint,
    _then_fingerprint,
    build_verification_matrix,
)
from src.exporters.customer_testspec_exporter import build_customer_testspec_preview
from web.code_style_samples import code_style_reference_for_bundle
from web.copilot_context_pack import _logic_block, build_context_pack
from web.gtest_workspace import generate_draft_for_request
from web.project_memory import merge_project_memory, patterns_for_logic


def _workbench_row(bundle: dict[str, Any], candidate_id: str, *, language: str = "EN") -> dict[str, Any] | None:
    preview = build_customer_testspec_preview(bundle, language=language)
    for row in preview.get("rows") or []:
        if str(row.get("candidate_id") or "") == candidate_id:
            return row
    return None


def _sibling_assertions(
    bundle: dict[str, Any],
    logic_id: str,
    given_fp: str,
    *,
    exclude_candidate: str = "",
) -> list[dict[str, Any]]:
    preview = build_customer_testspec_preview(bundle, language="EN")
    siblings: list[dict[str, Any]] = []
    for row in preview.get("rows") or []:
        if str(row.get("logic_id") or "") != logic_id:
            continue
        cid = str(row.get("candidate_id") or "")
        if cid == exclude_candidate:
            continue
        if _given_fingerprint(row.get("expected_input") or "") != given_fp:
            continue
        siblings.append(
            {
                "candidate_id": cid,
                "expected_output": row.get("expected_output") or "",
                "then_fingerprint": _then_fingerprint(row.get("expected_output") or ""),
            }
        )
    return siblings[:8]


def build_code_context_pack(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    library_root: Path | None = None,
    language: str = "EN",
    include_baseline: bool = True,
    cfg: dict[str, Any] | None = None,
    reference_test_name: str = "",
    library_code_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = _workbench_row(bundle, candidate_id, language=language)
    if not row:
        raise KeyError(f"Candidate not found in workbook: {candidate_id}")

    logic_id = str(row.get("logic_id") or "")
    if not logic_id:
        for cand in bundle.get("test_candidates") or []:
            if cand.get("id") == candidate_id:
                logic_id = _candidate_logic_id(cand) or ""
                break

    memory = merge_project_memory(library_root=library_root, bundle=bundle, gtest_state=gtest_state)
    matrix = build_verification_matrix(bundle, logic_id) if logic_id else {}
    given_fp = _given_fingerprint(row.get("expected_input") or "")
    style_ref = code_style_reference_for_bundle(
        bundle,
        reference_test_name=reference_test_name,
        library_samples=library_code_samples,
    )

    pack: dict[str, Any] = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "logic_id": logic_id,
        "testcase": {
            "candidate_id": candidate_id,
            "test_function": row.get("test_function"),
            "event": row.get("event"),
            "use_case": row.get("use_case"),
            "operation": row.get("operation"),
            "expected_input": row.get("expected_input"),
            "expected_output": row.get("expected_output"),
            "review_status": row.get("review_status"),
            "given_fingerprint": given_fp,
            "then_fingerprint": _then_fingerprint(row.get("expected_output") or ""),
        },
        "harness": gtest_state.get("harness") or {},
        "io_variable_map": memory.get("io_variable_map") or {},
        "signal_roles": memory.get("signal_roles") or {},
        "verification_patterns": patterns_for_logic(memory, logic_id),
        "verification_matrix": {
            "one_to_many_count": matrix.get("one_to_many_count", 0),
            "many_to_one_count": matrix.get("many_to_one_count", 0),
            "partial_assert_count": matrix.get("partial_assert_count", 0),
        },
        "sibling_assertions": _sibling_assertions(
            bundle, logic_id, given_fp, exclude_candidate=candidate_id
        ),
        "code_references": bundle.get("code_references") or [],
        "code_style_reference": style_ref,
    }

    if logic_id:
        lb = _logic_block(bundle, logic_id) or {}
        pack["logic"] = {
            "logic_id": logic_id,
            "control_name": lb.get("name") or row.get("control_name"),
            "raw_expression": str(lb.get("raw_expression") or lb.get("expression") or "")[:4000],
        }
        try:
            pack["logic_context"] = build_context_pack(bundle, logic_id, cfg=cfg)
        except (KeyError, ValueError, TypeError):
            pack["logic_context"] = {}

    if include_baseline:
        try:
            pack["baseline_skeleton"] = generate_draft_for_request(
                bundle,
                gtest_state,
                candidate_id=candidate_id,
                variable_map=memory.get("io_variable_map"),
                language=language,
            )
        except (KeyError, ValueError, TypeError):
            pack["baseline_skeleton"] = {}

    return pack
