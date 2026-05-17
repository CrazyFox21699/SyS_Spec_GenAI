from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.evidence_registry import build_evidence_registry
from src.models.evidence_model import format_locator, make_evidence_ref
from src.parsers.excel_parser import collect_merged_cell_evidence, extract_excel_workbook
from src.pipeline import run_analyze


def test_make_evidence_ref_has_required_fields() -> None:
    ref = make_evidence_ref(
        kind="table_merged_region",
        file="GPT_GenLogic.xlsx",
        locator="sheet Test / R21C1:R23C3",
        excerpt="SYS_SHUTOFF",
        confidence="high",
    )
    assert ref["id"].startswith("EVD_")
    assert ref["kind"] == "table_merged_region"
    assert ref["provenance"] == "deterministic"
    assert ref["review_required"] is True


def test_format_locator_from_source() -> None:
    loc = format_locator({"file": "a.xlsx", "sheet": "S1", "row": 5})
    assert "a.xlsx" in loc
    assert "sheet S1" in loc
    assert "row 5" in loc


def test_gpt_gen_logic_merged_cell_evidence() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "pm_sample_inputs" / "input" / "GPT_GenLogic.xlsx"
    if not path.exists():
        pytest.skip("GPT_GenLogic.xlsx not in sample_inputs")

    ex = extract_excel_workbook(path, [r"ADM\d+_[A-Z0-9_]+"])
    refs = ex.get("merged_cell_evidence") or []
    assert len(refs) >= 20
    kinds = {r["kind"] for r in refs}
    assert "table_merged_region" in kinds
    assert any("SYS_SHUTOFF" in (r.get("excerpt") or "") for r in refs)


def test_analyze_builds_evidence_registry() -> None:
    root = Path(__file__).resolve().parents[2]
    input_dir = root / "pm_sample_inputs" / "input"
    if not (input_dir / "GPT_GenLogic.xlsx").exists():
        pytest.skip("sample inputs missing")

    out = root / "pm_test_spec_assistant" / "output" / "_pytest_evidence_run"
    bundle = run_analyze(input_dir, out, Path(__file__).resolve().parents[1] / "config.yaml", force=True)
    reg = bundle.get("evidence_registry") or {}
    assert reg.get("total", 0) > 0
    assert bundle.get("product", {}).get("name") == "ALEX"
    merge_refs = [r for r in reg.get("items", []) if r.get("kind") == "table_merged_region"]
    assert len(merge_refs) >= 20


def test_build_evidence_registry_dedupes_ids() -> None:
    ref = make_evidence_ref(kind="alias", file="a.docx", excerpt="x -> y")
    reg = build_evidence_registry(alias_map=[{"alias": "x", "target": "y", "source": {"file": "a.docx"}}], extra_refs=[ref])
    assert reg["total"] >= 1
    assert len(reg["items"]) == len(reg["by_id"])
