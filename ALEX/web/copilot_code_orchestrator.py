"""Orchestrate hybrid GTest generation — Python baseline + M365 Copilot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from web.copilot_code_context_pack import build_code_context_pack
from web.copilot_code_writer import code_write_batch_size, run_code_write
from web.gtest_workspace import generate_draft_for_request, save_draft


def _candidate_has_io(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    inp = str(row.get("expected_input") or "").strip()
    out = str(row.get("expected_output") or "").strip()
    return bool(inp and out)


def run_copilot_code_generate(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_id: str,
    cfg: dict[str, Any],
    library_root: Path | None = None,
    engineer_note: str = "",
    use_baseline: bool = True,
    language: str = "EN",
    reference_test_name: str = "",
    library_code_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pack = build_code_context_pack(
        bundle,
        gtest_state,
        candidate_id=candidate_id,
        library_root=library_root,
        language=language,
        include_baseline=use_baseline,
        cfg=cfg,
        reference_test_name=reference_test_name,
        library_code_samples=library_code_samples,
    )
    baseline = pack.get("baseline_skeleton") or {}
    if not baseline and use_baseline:
        baseline = generate_draft_for_request(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            variable_map=pack.get("io_variable_map"),
            language=language,
        )
        pack["baseline_skeleton"] = baseline

    copilot_result = run_code_write(pack, cfg, engineer_note=engineer_note)
    copilot_draft = copilot_result.get("draft") or {}

    return {
        "ok": copilot_result.get("ok"),
        "context_pack": pack,
        "baseline": baseline,
        "copilot_draft": copilot_draft,
        "validation": copilot_result.get("validation") or {},
        "provider": copilot_result.get("provider"),
        "error": None if copilot_result.get("ok") else "Copilot did not return valid GTest JSON",
        "raw_preview": copilot_result.get("raw_preview"),
    }


def run_copilot_code_generate_batch(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    candidate_ids: list[str],
    cfg: dict[str, Any],
    library_root: Path | None = None,
    engineer_note: str = "",
    language: str = "EN",
    reference_test_name: str = "",
    library_code_samples: list[dict[str, Any]] | None = None,
    persist_drafts: bool = False,
) -> dict[str, Any]:
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

    preview = build_customer_testspec_preview(bundle, language=language)
    row_by_id = {str(r.get("candidate_id") or ""): r for r in preview.get("rows") or []}
    batch_size = code_write_batch_size(cfg)
    results: list[dict[str, Any]] = []
    ok_count = 0
    skip_count = 0

    for cid in candidate_ids:
        row = row_by_id.get(cid)
        if not _candidate_has_io(row):
            results.append(
                {
                    "candidate_id": cid,
                    "ok": False,
                    "skipped": True,
                    "reason": "missing_expected_io",
                }
            )
            skip_count += 1
            continue

        try:
            one = run_copilot_code_generate(
                bundle,
                gtest_state,
                candidate_id=cid,
                cfg=cfg,
                library_root=library_root,
                engineer_note=engineer_note,
                language=language,
                reference_test_name=reference_test_name,
                library_code_samples=library_code_samples,
            )
        except KeyError as exc:
            results.append({"candidate_id": cid, "ok": False, "error": str(exc)})
            continue

        entry: dict[str, Any] = {
            "candidate_id": cid,
            "ok": one.get("ok"),
            "copilot_draft": one.get("copilot_draft") or {},
            "validation": one.get("validation") or {},
            "error": one.get("error"),
        }
        if one.get("ok"):
            ok_count += 1
            if persist_drafts and entry["copilot_draft"].get("full_snippet"):
                save_draft(
                    gtest_state,
                    draft_key=cid,
                    draft={
                        **entry["copilot_draft"],
                        "source_kind": "copilot",
                    },
                    engineer_edited=False,
                )
        results.append(entry)

        if len([r for r in results if not r.get("skipped")]) % batch_size == 0:
            pass  # pacing hook for future rate-limit sleep

    gtest_state.setdefault("copilot_batch", {})["last_results"] = results
    gtest_state["updated_at"] = gtest_state.get("updated_at") or ""

    return {
        "ok": ok_count > 0,
        "total": len(candidate_ids),
        "generated": ok_count,
        "skipped": skip_count,
        "failed": len(candidate_ids) - ok_count - skip_count,
        "results": results,
        "batch_size": batch_size,
    }
