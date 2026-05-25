"""Orchestrate hybrid GTest generation — Python baseline + M365 Copilot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from web.copilot_code_context_pack import build_code_context_pack
from web.copilot_code_writer import run_code_write
from web.gtest_workspace import generate_draft_for_request


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
) -> dict[str, Any]:
    pack = build_code_context_pack(
        bundle,
        gtest_state,
        candidate_id=candidate_id,
        library_root=library_root,
        language=language,
        include_baseline=use_baseline,
        cfg=cfg,
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
        "provider": copilot_result.get("provider"),
        "error": None if copilot_result.get("ok") else "Copilot did not return valid GTest JSON",
        "raw_preview": copilot_result.get("raw_preview"),
    }
